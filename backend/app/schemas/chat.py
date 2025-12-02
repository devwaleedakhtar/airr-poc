from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language user question")
    top_k_tables: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of tables to include in the answer prompt",
    )
    force_metadata_only: bool = Field(
        default=False,
        description="Skip table JSON and answer only from schema descriptions (definitional mode).",
    )


class TableMetadata(BaseModel):
    row_count: int | None = None
    columns_present: List[str] = Field(default_factory=list)
    row_labels: List[str] = Field(default_factory=list)
    truncated: bool = False
    notes: List[str] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    answer: str
    tables_used: List[str] = Field(default_factory=list)
    metadata_only: bool = False
    intent: str = Field(default="data")
    table_metadata: Dict[str, TableMetadata] = Field(default_factory=dict)
    guardrail_messages: List[str] = Field(default_factory=list)


