"""Profile update and statistics response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    department: str | None = Field(default=None, max_length=150)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    department: str | None


class ProfileStatisticsResponse(BaseModel):
    total_analyses: int
    completed_analyses: int
    needs_review: int