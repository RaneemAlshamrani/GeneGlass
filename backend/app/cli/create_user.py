"""Interactively create a GeneGlass user with a hashed password."""

import argparse
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db.init_db import initialize_database
from app.db.session import SessionLocal
from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.services.users import create_user, get_user_by_email


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a GeneGlass user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--department")
    parser.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.SPECIALIST.value,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    initialize_database()

    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1

    try:
        user_data = UserCreate(
            full_name=args.full_name,
            email=args.email,
            password=password,
            department=args.department,
            role=UserRole(args.role),
        )
    except ValidationError as exc:
        print(exc)
        return 1

    with SessionLocal() as session:
        if get_user_by_email(session, str(user_data.email)) is not None:
            print("A user with this email already exists.")
            return 1
        try:
            user = create_user(session, user_data)
        except IntegrityError:
            session.rollback()
            print("Could not create the user because the email already exists.")
            return 1

    print(f"Created user #{user.id}: {user.email} ({user.role.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
