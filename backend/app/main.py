"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import auth_router
from app.api.routes import api_router, health_router
from app.core.config import get_settings
from app.db.init_db import initialize_database


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Initialize shared application resources before serving requests."""

    initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend API for the GeneGlass graduation project.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
    )

    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_prefix)
    application.include_router(auth_router, prefix=settings.api_prefix)
    return application



app = create_app()
