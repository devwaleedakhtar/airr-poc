from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class UploadWorkbookResponse(BaseModel):
    workbook_id: str = Field(...)
    sheets: List[str] = Field(default_factory=list)


class ConvertRequest(BaseModel):
    sheet_name: str


class ConvertResponse(BaseModel):
    pdf_url: str


class ExtractRequest(BaseModel):
    sheet_name: Optional[str] = None


class ExtractResponse(BaseModel):
    session_id: str
    extracted_json: dict
    confidences: dict | None = None
    inferred_tables: list[str] | None = None
    warnings: list[str] | None = None

