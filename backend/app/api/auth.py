
"""OAuth2 login, current-user, and password-change endpoints."""


from app.core.config import get_settings
from app.services.password_reset import (
    create_reset_token,
    get_reset_token_user_id,
    consume_reset_token,
    invalidate_reset_token,
    invalidate_reset_tokens_for_user,
)
from app.services.password_reset_email import (
    PasswordResetEmailError,
    send_password_reset_email,
)
import logging


from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
   ForgotPasswordRequest,
   ResetPasswordRequest,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.users import (
    authenticate_user,
    create_user,
    get_user_by_email,
)
from app.services.audit import AuditAction, add_audit_event
from app.services.login_rate_limit import (
    forgot_password_rate_limiter,
    login_rate_limiter,
    register_rate_limiter,
    reset_password_rate_limiter,
)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])
_reset_logger = logging.getLogger(__name__)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in with email and password",
)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    # Use the actual ASGI client address, not an untrusted forwarded header.
    client_ip = request.client.host if request.client else "unknown"
    retry_after = login_rate_limiter.reserve(client_ip, form_data.username)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate_user(
        session,
        form_data.username,
        form_data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    add_audit_event(
        session,
        actor_id=user.id,
        action=AuditAction.LOGIN_SUCCEEDED,
    )
    session.commit()
    # A session is valid only while this user's password hash is unchanged.
    token, expires_in = create_access_token(user.id, user.password_hash)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@auth_router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the signed-in user",
)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@auth_router.post(
    "/change-password",
    summary="Change the signed-in user's password",
)
def change_password(
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    if (
        current_user.password_hash is None
        or not verify_password(
            password_data.current_password,
            current_user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    current_user.password_hash = hash_password(password_data.new_password)

    add_audit_event(
        session,
        actor_id=current_user.id,
        action=AuditAction.PASSWORD_CHANGED,
    )
    # Revoke any reset email already issued for this account.
    invalidate_reset_tokens_for_user(current_user.id)
    session.commit()

    return {"message": "Password changed successfully."}




@auth_router.post(
    "/forgot-password",
    summary="Email a password-reset link",
)
def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    email = str(request.email).strip().lower()
    client_ip = http_request.client.host if http_request.client else "unknown"
    retry_after = forgot_password_rate_limiter.reserve(client_ip, email)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    settings = get_settings()
    if not settings.smtp_email or not settings.smtp_app_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured.",
        )

    user = get_user_by_email(session, email)
    if user is not None and user.is_active:
        token = create_reset_token(user.id)
        if token is not None:
            try:
                send_password_reset_email(email, token)
            except PasswordResetEmailError as error:
                invalidate_reset_token(token)
                # Never log the recipient, token, SMTP password, or reset URL.
                _reset_logger.error("Reset email delivery failed (%s)", type(error).__name__)
                # A uniform public response prevents revealing registered addresses.

    return {"message": "If the account exists, a reset link has been sent."}


@auth_router.post(
    "/reset-password",
    summary="Reset password using an emailed one-time link",
)
def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    client_ip = http_request.client.host if http_request.client else "unknown"
    retry_after = reset_password_rate_limiter.reserve(client_ip, request.token)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user_id = get_reset_token_user_id(request.token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    if user.password_hash and verify_password(request.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    if consume_reset_token(request.token) != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    user.password_hash = hash_password(request.new_password)
    add_audit_event(session, actor_id=user.id, action=AuditAction.PASSWORD_CHANGED)
    session.commit()
    return {"message": "Password reset successfully."}


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new specialist account",
)
def register(
    request: Request,
    user_data: UserCreate,
    session: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    email = str(user_data.email).strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    retry_after = register_rate_limiter.reserve(client_ip, email)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    if get_user_by_email(session, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    specialist_data = user_data.model_copy(
        update={"role": UserRole.SPECIALIST}
    )

    try:
        user = create_user(session, specialist_data)
    except IntegrityError:
        # Another request may have registered the same email between lookup
        # and INSERT. Handle that race without exposing database details.
        session.rollback()
        if get_user_by_email(session, email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            ) from None
        raise

    return UserResponse.model_validate(user)
