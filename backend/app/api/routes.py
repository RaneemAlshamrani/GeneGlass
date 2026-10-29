"""Initial public endpoints for the GeneGlass API."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import database_is_available
from app.schemas.system import ApiRootResponse, HealthResponse

health_router = APIRouter(tags=["system"])
api_router = APIRouter(tags=["api"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API health",
)
def health_check() -> HealthResponse:
    settings = get_settings()
    try:
        database_connected = database_is_available()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        ) from exc

    if not database_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        database="connected",
    )


@api_router.get(
    "",
    response_model=ApiRootResponse,
    summary="GeneGlass API entry point",
)
@api_router.get(
    "/",
    response_model=ApiRootResponse,
    summary="GeneGlass API entry point",
    include_in_schema=False,
)
async def api_root() -> ApiRootResponse:
    settings = get_settings()
    return ApiRootResponse(
        name=settings.app_name,
        status="ready",
        version=settings.app_version,
        docs="/docs",
    )
