
"""Create and inspect the GeneGlass SQLite schema."""

from sqlalchemy import Engine, inspect

import app.models  # noqa: F401 - registers models in Base.metadata
from app.db.base import Base
from app.db.session import engine


QUALITY_COLUMNS = {
    "sequence_length": "INTEGER",
    "cleaned_sequence_length": "INTEGER",
    "average_quality": "FLOAT",
    "minimum_quality": "INTEGER",
    "maximum_quality": "INTEGER",
    "low_quality_count": "INTEGER",
    "low_quality_percentage": "FLOAT",
    "retained_percentage": "FLOAT",
    "quality_assessment": "VARCHAR(20)",
}


def initialize_database(target_engine: Engine = engine) -> list[str]:
    """Create missing tables and safely add missing quality columns."""

    Base.metadata.create_all(bind=target_engine)

    inspector = inspect(target_engine)
    if "analyses" in inspector.get_table_names():
        existing_columns = {
            column["name"]
            for column in inspector.get_columns("analyses")
        }

        with target_engine.begin() as connection:
            for column_name, column_type in QUALITY_COLUMNS.items():
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE analyses "
                        f"ADD COLUMN {column_name} {column_type}"
                    )

    return sorted(inspect(target_engine).get_table_names())


if __name__ == "__main__":
    tables = initialize_database()
    print("GeneGlass database is ready.")
    print(f"Tables: {', '.join(tables)}")
