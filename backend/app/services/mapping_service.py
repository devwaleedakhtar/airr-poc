from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from openai import OpenAI
from pydantic import ValidationError

from ..core.config import settings
from ..schemas.mapping import MappingMetadata, MappingResult, MissingField

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_SCHEMA_PATH = BASE_DIR / "constants" / "model_schema.yaml"
MAPPING_PROMPT_PATH = BASE_DIR / "prompts" / "mapping_prompt.txt"


@lru_cache(maxsize=1)
def _load_model_schema() -> Dict[str, Any]:
    with MODEL_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def _schema_version() -> str:
    raw = MODEL_SCHEMA_PATH.read_text(encoding="utf-8")
    return sha1(raw.encode("utf-8")).hexdigest()[:12]


@lru_cache(maxsize=1)
def _canonical_catalog() -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, Dict[str, str]]]:
    schema = _load_model_schema()
    table_fields: Dict[str, List[str]] = {}
    table_labels: Dict[str, str] = {}
    field_labels: Dict[str, Dict[str, str]] = {}

    def add_section(section: Dict[str, Any], bucket: Dict[str, str], order: List[str]):
        if not isinstance(section, dict):
            return
        for field_name, field_meta in section.items():
            if field_name not in bucket:
                order.append(field_name)
            bucket[field_name] = field_meta.get("label") or field_name

    for table in schema.get("tables", []):
        table_name = table.get("name")
        if not table_name:
            continue
        table_labels[table_name] = table.get("label") or table_name
        field_labels[table_name] = {}
        table_fields[table_name] = []

        add_section(table.get("fields") or {}, field_labels[table_name], table_fields[table_name])
        add_section(table.get("columns") or {}, field_labels[table_name], table_fields[table_name])
        add_section(table.get("series") or {}, field_labels[table_name], table_fields[table_name])
        summary_fields = (table.get("summary_row") or {}).get("fields") or {}
        add_section(summary_fields, field_labels[table_name], table_fields[table_name])

    return table_fields, table_labels, field_labels


@lru_cache(maxsize=1)
def _table_fields() -> Dict[str, List[str]]:
    return _canonical_catalog()[0]


@lru_cache(maxsize=1)
def _table_labels() -> Dict[str, str]:
    return _canonical_catalog()[1]


@lru_cache(maxsize=1)
def _field_labels() -> Dict[str, Dict[str, str]]:
    return _canonical_catalog()[2]


@lru_cache(maxsize=1)
def _schema_summary() -> str:
    schema = _load_model_schema()
    lines: List[str] = []

    def describe_fields(section: Dict[str, Any], prefix: str = ""):
        if not isinstance(section, dict):
            return []
        entries = []
        for field_name, field_meta in section.items():
            aliases = field_meta.get("aliases") or []
            alias_text = f" | aliases: {', '.join(aliases)}" if aliases else ""
            field_label = field_meta.get("label")
            field_type = field_meta.get("type")
            field_desc = field_meta.get("description")
            entries.append(
                f"  - {prefix}{field_name} ({field_type}) :: {field_label} - {field_desc}{alias_text}"
            )
        return entries

    for table in schema.get("tables", []):
        table_name = table.get("name")
        label = table.get("label")
        description = table.get("description")
        lines.append(f"{table_name} :: {label} - {description}")
        lines.extend(describe_fields(table.get("fields") or {}))
        lines.extend(describe_fields(table.get("columns") or {}, "column: "))
        lines.extend(describe_fields(table.get("series") or {}, "series: "))
        summary_fields = (table.get("summary_row") or {}).get("fields") or {}
        lines.extend(describe_fields(summary_fields, "summary: "))
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _base_mapping_prompt() -> str:
    try:
        return MAPPING_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "You map extracted values into the canonical schema. Follow the provided schema exactly."
        )


def _build_prompt(source_json: Dict[str, Any]) -> str:
    summary = _schema_summary()
    source_text = json.dumps(source_json, indent=2, ensure_ascii=False)
    base = _base_mapping_prompt()
    return (
        f"{base}\n\nCanonical Schema Definition:\n{summary}\n\n"
        f"Source JSON (table -> field -> value):\n{source_text}\n\n"
        "Return JSON strictly following the MappingResult schema. "
        "Every canonical field must be present under its table in `mapped` (use null for missing).\n"
        "Populate `missing_fields` with any canonical fields you could not confidently map. "
        "If everything is mapped with confidence, return an empty list."
    )


def _ensure_canonical_shape(mapped: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    canonical: Dict[str, Dict[str, Any]] = {}
    fields_by_table = _table_fields()
    for table_name, field_names in fields_by_table.items():
        canonical[table_name] = {}
        source_fields = mapped.get(table_name, {}) if isinstance(mapped, dict) else {}
        for field_name in field_names:
            value = None
            if isinstance(source_fields, dict):
                value = source_fields.get(field_name)
            canonical[table_name][field_name] = value
    # ensure tables with no explicit fields still appear
    for table_name in fields_by_table.keys():
        canonical.setdefault(table_name, {})
    return canonical


def _normalize_missing_fields(
    missing_fields: List[MissingField], canonical: Dict[str, Dict[str, Any]]
) -> List[MissingField]:
    table_labels = _table_labels()
    field_labels = _field_labels()
    normalized: List[MissingField] = []
    seen: set[Tuple[str, str]] = set()

    for item in missing_fields or []:
        if item.table not in canonical:
            continue
        if field_labels.get(item.table) and item.field not in field_labels[item.table]:
            continue
        item.table_label = item.table_label or table_labels.get(item.table)
        item.field_label = item.field_label or field_labels.get(item.table, {}).get(item.field)
        normalized.append(item)
        seen.add((item.table, item.field))

    for table, fields in canonical.items():
        labels = field_labels.get(table, {})
        for field_name, value in fields.items():
            if (table, field_name) in seen:
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                normalized.append(
                    MissingField(
                        table=table,
                        field=field_name,
                        reason="Value missing after mapping",
                        confidence=None,
                        table_label=table_labels.get(table),
                        field_label=labels.get(field_name),
                    )
                )
                seen.add((table, field_name))
    return normalized


def _finalize_mapping(result: MappingResult) -> MappingResult:
    canonical = _ensure_canonical_shape(result.mapped)
    missing = _normalize_missing_fields(result.missing_fields or [], canonical)
    metadata = result.metadata or MappingMetadata()
    metadata.generated_at = datetime.utcnow()
    metadata.model_version = metadata.model_version or _schema_version()
    table_labels = _table_labels()
    field_labels = _field_labels()
    metadata.table_labels = dict(table_labels)
    metadata.field_labels = {table: dict(fields) for table, fields in field_labels.items()}
    return MappingResult(mapped=canonical, missing_fields=missing, metadata=metadata)


def map_to_canonical(source_json: Dict[str, Any]) -> MappingResult:
    if not source_json:
        raise ValueError("Source JSON is empty; cannot perform mapping.")

    prompt = _build_prompt(source_json)
    client = OpenAI(api_key=settings.model_api_key, base_url=settings.openai_base_url)
    response = client.chat.completions.create(
        model=settings.model_name,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You output canonical JSON mappings only. Follow instructions exactly.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content if response.choices else "{}"
    try:
        parsed = MappingResult.model_validate_json(content or "{}")
    except ValidationError:
        data = json.loads(content or "{}")
        parsed = MappingResult.model_validate(data)

    return _finalize_mapping(parsed)


def normalize_mapping(mapping: MappingResult) -> MappingResult:
    """Normalize a mapping payload from the client before persisting."""
    return _finalize_mapping(mapping)
