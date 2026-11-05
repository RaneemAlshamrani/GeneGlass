"""Apply Alembic migrations and baseline compatible legacy databases."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

import app.models  # noqa: F401 - registers every model in Base.metadata
from app.db.base import Base
from app.db.session import engine

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def build_alembic_config(target_engine: Engine = engine) -> Config:
    """Build an Alembic config for the selected SQLAlchemy engine."""

    config = Config(str(ALEMBIC_INI))
    database_url = target_engine.url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _validate_legacy_schema(target_engine: Engine) -> None:
    """Refuse to stamp a partial or outdated pre-Alembic database."""

    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)
    missing_tables = expected_tables - existing_tables
    missing_columns = {}

    for table_name in expected_tables & existing_tables:
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        expected_columns = set(Base.metadata.tables[table_name].columns.keys())
        missing = sorted(expected_columns - existing_columns)
        if missing:
            missing_columns[table_name] = missing

    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(sorted(missing_tables))}")
        if missing_columns:
            formatted = "; ".join(
                f"{table}: {', '.join(columns)}"
                for table, columns in sorted(missing_columns.items())
            )
            details.append(f"missing columns: {formatted}")
        raise RuntimeError(
            "Legacy database does not match the GeneGlass migration baseline ("
            + "; ".join(details)
            + "). Back up the database and migrate it explicitly before startup."
        )


def initialize_database(target_engine: Engine = engine) -> list[str]:
    """Upgrade a database to head, safely baselining the current legacy schema."""

    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    application_tables = set(Base.metadata.tables)
    config = build_alembic_config(target_engine)

    if "alembic_version" not in existing_tables and (
        existing_tables & application_tables
    ):
        _validate_legacy_schema(target_engine)
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")

    return sorted(inspect(target_engine).get_table_names())


if __name__ == "__main__":
    tables = initialize_database()
    print("GeneGlass database migrations are up to date.")
    print(f"Tables: {', '.join(tables)}")
