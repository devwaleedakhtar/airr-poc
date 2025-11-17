from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MissingField(BaseModel):
    table: str = Field(..., description="Canonical table name defined in model_schema.yaml")
    field: str = Field(..., description="Canonical field name defined in model_schema.yaml")
    reason: str = Field(..., description="Short explanation of why the value is missing")
    confidence: Optional[str] = Field(
        default=None,
        description="Optional qualitative confidence score (e.g., high/medium/low)",
    )
    source_fields: Optional[List[str]] = Field(
        default=None,
        description="Optional list of source field names that might map here",
    )
    table_label: Optional[str] = Field(
        default=None,
        description="Readable label for the canonical table",
    )
    field_label: Optional[str] = Field(
        default=None,
        description="Readable label for the canonical field",
    )


class MappingMetadata(BaseModel):
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp for when the mapping was generated",
    )
    warnings: Optional[List[str]] = Field(default=None)
    model_version: Optional[str] = Field(
        default=None, description="Optional identifier for the canonical schema version"
    )
    table_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Lookup of canonical table names to their labels",
    )
    field_labels: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Lookup of canonical field names (per table) to their labels",
    )


class MappingResult(BaseModel):
    mapped: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Canonical-shaped object keyed by table and field names",
    )
    missing_fields: List[MissingField] = Field(default_factory=list)
    metadata: MappingMetadata = Field(default_factory=MappingMetadata)
