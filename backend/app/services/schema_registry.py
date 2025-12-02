from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_SCHEMA_PATH = BASE_DIR / "constants" / "model_schema.yaml"


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    label: str | None = None
    description: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TableSchema:
    name: str
    label: str | None
    description: str | None
    row_match_strategy: str | None
    row_key_field: str | None
    columns: list[ColumnSchema]

    @property
    def all_alias_text(self) -> str:
        alias_chunks: list[str] = []
        for column in self.columns:
            alias_chunks.extend(column.aliases or [])
        return " ".join(alias_chunks)

    @property
    def selection_text(self) -> str:
        column_bits = []
        for column in self.columns:
            alias_text = ", ".join(column.aliases) if column.aliases else ""
            column_bits.append(
                f"{column.name} ({column.label or ''}) {column.description or ''} {alias_text}"
            )
        joined_columns = " | ".join(column_bits)
        return (
            f"{self.name} {self.label or ''} {self.description or ''} "
            f"{self.row_match_strategy or ''} columns: {joined_columns}"
        )


def _load_raw_schema() -> Dict[str, Dict]:
    raw = yaml.safe_load(MODEL_SCHEMA_PATH.read_text(encoding="utf-8")) or {}
    return raw.get("model_schema") or raw


@lru_cache(maxsize=1)
def _load_table_schemas() -> Dict[str, TableSchema]:
    schema = _load_raw_schema()
    tables: Dict[str, TableSchema] = {}
    for name, section in schema.items():
        if not isinstance(section, dict):
            continue
        if section.get("kind") not in ["table", "scalar_group"]:
            continue
        if section.get("kind") == "table":
            columns_meta = section.get("columns") or {}
        elif section.get("kind") == "scalar_group":
            columns_meta = section.get("fields") or {}
        columns: List[ColumnSchema] = []
        # TODO: Handle canonical items for tables. (other income)
        for col_name, col_meta in columns_meta.items():
            columns.append(
                ColumnSchema(
                    name=col_name,
                    label=col_meta.get("label"),
                    description=col_meta.get("description"),
                    aliases=list(col_meta.get("aliases") or []),
                )
            )
        tables[name] = TableSchema(
            name=name,
            label=section.get("label"),
            description=section.get("description"),
            row_match_strategy=section.get("row_match_strategy"),
            row_key_field=section.get("row_key_field"),
            columns=columns,
        )
    return tables


def list_table_schemas() -> list[TableSchema]:
    return list(_load_table_schemas().values())


def get_table_schema(name: str) -> TableSchema | None:
    return _load_table_schemas().get(name)


def available_table_names() -> list[str]:
    return list(_load_table_schemas().keys())


