"""Create and inspect the GeneGlass SQLite schema."""

from sqlalchemy import Engine, inspect

import app.models  # noqa: F401 - registers models in Base.metadata
from app.db.base import Base
from app.db.session import engine


def initialize_database(target_engine: Engine = engine) -> list[str]:
    """Create missing tables without deleting or replacing existing data."""

    Base.metadata.create_all(bind=target_engine)
    return sorted(inspect(target_engine).get_table_names())


if __name__ == "__main__":
    tables = initialize_database()
    print("GeneGlass database is ready.")
    print(f"Tables: {', '.join(tables)}")
