
"""OAuth2 login, current-user, and password-change endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    TokenResponse,
    UserResponse,
)
from app.services.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.users import authenticate_user

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

    session.commit()

    return {"message": "Password changed successfully."}
