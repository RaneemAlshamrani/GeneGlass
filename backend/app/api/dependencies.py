"""Reusable FastAPI authentication dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.security import decode_access_token, matches_session_stamp

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_error

    user_id, token_stamp = token_data
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    if not matches_session_stamp(user.id, user.password_hash, token_stamp):
        raise credentials_error
    return user
