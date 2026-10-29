"""User persistence and authentication services."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import UserCreate
from app.services.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    verify_password,
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == normalize_email(email))
    )


def create_user(session: Session, user_data: UserCreate) -> User:
    user = User(
        full_name=user_data.full_name.strip(),
        email=normalize_email(str(user_data.email)),
        password_hash=hash_password(user_data.password),
        department=(
            user_data.department.strip() if user_data.department else None
        ),
        role=user_data.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    email: str,
    password: str,
) -> User | None:
    user = get_user_by_email(session, email)
    if user is None or user.password_hash is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user
