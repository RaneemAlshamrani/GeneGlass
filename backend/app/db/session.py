"""SQLite engine and request-scoped SQLAlchemy sessions."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create a SQLite engine with foreign-key enforcement enabled."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{database_path.as_posix()}"
    sqlite_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    @event.listens_for(sqlite_engine, "connect")
    def enable_foreign_keys(
        dbapi_connection: Any,
        _connection_record: Any,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine


settings = get_settings()
engine = create_sqlite_engine(settings.database_path)
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session and always close it after the request."""

    with SessionLocal() as session:
        yield session


def database_is_available(target_engine: Engine = engine) -> bool:
    """Run a minimal query to verify the configured database connection."""

    with target_engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
