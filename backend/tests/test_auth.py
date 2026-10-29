from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.init_db import initialize_database
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.schemas.auth import UserCreate
from app.services.users import create_user


@pytest.fixture
def auth_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    test_engine = create_sqlite_engine(tmp_path / "auth.db")
    initialize_database(test_engine)
    test_sessions = sessionmaker(
        bind=test_engine,
        class_=Session,
        expire_on_commit=False,
    )

    with test_sessions() as session:
        create_user(
            session,
            UserCreate(
                full_name="Test Specialist",
                email="specialist@example.com",
                password="CorrectPassword123!",
                department="Genetics Laboratory",
            ),
        )

    def override_get_db() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_login_and_current_user(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/auth/login",
        data={
            "username": "SPECIALIST@EXAMPLE.COM",
            "password": "CorrectPassword123!",
        },
    )

    assert login_response.status_code == 200
    token_data = login_response.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 3600
    assert token_data["user"]["email"] == "specialist@example.com"

    me_response = auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["full_name"] == "Test Specialist"


def test_login_rejects_wrong_password(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/login",
        data={
            "username": "specialist@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_current_user_requires_token(auth_client: TestClient) -> None:
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 401
