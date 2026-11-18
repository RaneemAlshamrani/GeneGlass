
"""OAuth2 login, current-user, and password-change endpoints."""


from app.core.config import get_settings
from app.services.password_reset import (
    create_reset_token,
    consume_reset_token,
)


from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
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

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in with email and password",
)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
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
    token, expires_in = create_access_token(user.id)

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
    session.commit()

    return {"message": "Password changed successfully."}


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new specialist account",
)


@auth_router.post(
    "/forgot-password",
    summary="Request a password-reset token",
)


def forgot_password(
    request: ForgotPasswordRequest,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    email = str(request.email).strip().lower()
    user = get_user_by_email(session, email)

    # Always return the same response to avoid revealing registered emails.
    if user is not None and user.is_active:
        settings = get_settings()

        if settings.app_env.lower() == "development":
            token = create_reset_token(user.id)
            print(f"\n[GeneGlass] Password reset token: {token}\n")

    return {
        "message": "If the account exists, a reset token has been generated."
    }


@auth_router.post(
    "/reset-password",
    summary="Reset password using a valid token",
)
def reset_password(
    request: ResetPasswordRequest,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    user_id = consume_reset_token(request.token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user.password_hash = hash_password(request.new_password)
    session.commit()

    return {"message": "Password reset successfully."}

def register(
    user_data: UserCreate,
    session: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    email = str(user_data.email).strip().lower()

    if get_user_by_email(session, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    specialist_data = user_data.model_copy(
        update={"role": UserRole.SPECIALIST}
    )

    user = create_user(session, specialist_data)

    return UserResponse.model_validate(user)
