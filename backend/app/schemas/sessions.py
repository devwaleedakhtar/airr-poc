from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .mapping import MappingJobStatus, MappingResult


class ExportAppliedField(BaseModel):
    table: str
    field: str
    cell: str
    value: Any | None = None


class ExportResponse(BaseModel):
    download_url: str
    applied_fields: list[ExportAppliedField] = Field(default_factory=list)


class SessionModel(BaseModel):
    id: str = Field(..., alias="_id")
    workbook_id: str
    sheet_name: str
    pdf_url: str
    extracted_json: Dict[str, Any]
    confidences: Optional[Dict[str, Any]] = None
    inferred_tables: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    text_snippets: Optional[Dict[str, str]] = None
    final_json: Optional[Dict[str, Any]] = None
    mapping: Optional[MappingResult] = None
    mapping_job: Optional[MappingJobStatus] = None
    created_at: datetime
    updated_at: datetime


class SessionListItem(BaseModel):
    id: str = Field(..., alias="_id")
    workbook_id: str
    sheet_name: str
    created_at: datetime
    updated_at: datetime


class UpdateSessionRequest(BaseModel):
    final_json: Dict[str, Any]
