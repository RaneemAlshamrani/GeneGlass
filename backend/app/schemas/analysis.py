
"""Analysis list and detail response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalysisListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_file_name: str
    gene: str
    target_variant: str
    status: str
    qc_status: str
    v617f_detected: bool | None
    created_at: datetime


class AnalysisDetailResponse(AnalysisListItem):
    stored_file_path: str | None
    result_summary: str | None
    error_message: str | None
    completed_at: datetime | None


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
