"""Validated application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the GeneGlass API."""

    app_name: str = "GeneGlass API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_path: Path = Path("data/geneglass.db")
    jwt_secret_key: str = "development-only-change-this-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        return value

    @field_validator("database_path")
    @classmethod
    def resolve_database_path(cls, value: Path) -> Path:
        """Resolve relative database paths from the backend directory."""

        if value.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
            raise ValueError("DATABASE_PATH must point to a SQLite database file")
        if not value.is_absolute():
            value = BACKEND_DIR / value
        return value.resolve()

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("access_token_expire_minutes")
    @classmethod
    def validate_token_lifetime(cls, value: int) -> int:
        if not 5 <= value <= 1440:
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 1440"
            )
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",")]
        origins = [origin for origin in origins if origin]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' because credentials are enabled"
            )
        if any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise ValueError("Every CORS origin must start with http:// or https://")
        return ",".join(origins)

    @property
    def cors_origin_list(self) -> list[str]:
        """Return the configured comma-separated origins as a clean list."""

        return self.cors_origins.split(",")


@lru_cache
def get_settings() -> Settings:
    """Create settings once and reuse them for the application lifetime."""

    return Settings()
