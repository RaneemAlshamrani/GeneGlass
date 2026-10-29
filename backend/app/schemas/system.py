"""Schemas for public system endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    database: Literal["connected"]


class ApiRootResponse(BaseModel):
    name: str
    status: Literal["ready"]
    version: str
    docs: str
