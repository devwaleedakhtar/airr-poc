from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List

import yaml
from openai import OpenAI
from pydantic import ValidationError
try:
    import tiktoken
except ImportError:
    tiktoken = None

from ..core.config import settings
from ..schemas.mapping import MappingMetadata, MappingResult, MissingField

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_SCHEMA_PATH = BASE_DIR / "constants" / "model_schema.yaml"
MAPPING_PROMPT_PATH = BASE_DIR / "prompts" / "mapping_prompt.txt"
logger = logging.getLogger(__name__)
# Ensure mapping logs emit at INFO even when the root logger is stricter.
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _raw_schema_text() -> str:
    return MODEL_SCHEMA_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _schema_version() -> str:
    raw = _raw_schema_text()
    return sha1(raw.encode("utf-8")).hexdigest()[:12]


@lru_cache(maxsize=1)
def _load_model_schema() -> Dict[str, Any]:
    raw = yaml.safe_load(_raw_schema_text()) or {}
    return raw.get("model_schema") or raw


@lru_cache(maxsize=1)
def _schema_sections() -> Dict[str, Dict[str, Any]]:
    """Return only the domain sections (skip name/version/description/etc.)."""
    schema = _load_model_schema()
    sections: Dict[str, Dict[str, Any]] = {}
    for key, value in schema.items():
        if key in {"name", "version", "description", "conventions", "mapping_guidance"}:
            continue
        if isinstance(value, dict) and value.get("kind"):
            sections[key] = value
    return sections


@lru_cache(maxsize=1)
def _table_fields() -> Dict[str, List[str]]:
    """Flatten per-section field/column names to support missing-field scaffolding."""
    out: Dict[str, List[str]] = {}
    for name, section in _schema_sections().items():
        kind = section.get("kind")
        if kind == "scalar_group":
            fields = section.get("fields") or {}
            out[name] = list(fields.keys())
        elif kind == "table":
            columns = section.get("columns") or {}
            out[name] = list(columns.keys())
    return out


@lru_cache(maxsize=1)
def _table_labels() -> Dict[str, str]:
    return {name: section.get("label") or name for name, section in _schema_sections().items()}


@lru_cache(maxsize=1)
def _field_labels() -> Dict[str, Dict[str, str]]:
    labels: Dict[str, Dict[str, str]] = {}
    for name, section in _schema_sections().items():
        kind = section.get("kind")
        labels[name] = {}
        if kind == "scalar_group":
            for fname, fmeta in (section.get("fields") or {}).items():
                labels[name][fname] = fmeta.get("label") or fname
        elif kind == "table":
            for cname, cmeta in (section.get("columns") or {}).items():
                labels[name][cname] = cmeta.get("label") or cname
    return labels


@lru_cache(maxsize=1)
def _schema_summary() -> str:
    """Readable summary of the canonical schema for the prompt."""
    sections = _schema_sections()
    lines: List[str] = []

    def field_line(field_name: str, meta: Dict[str, Any]) -> str:
        aliases = meta.get("aliases") or []
        alias_txt = f" | aliases: {', '.join(aliases)}" if aliases else ""
        dtype = meta.get("dtype") or meta.get("type")
        role = meta.get("role")
        label = meta.get("label") or field_name
        desc = meta.get("description") or ""
        return f"  - {field_name} [{role or 'input'}; {dtype or 'string'}] :: {label}{alias_txt} - {desc}"

    for name, section in sections.items():
        kind = section.get("kind")
        label = section.get("label") or name
        desc = section.get("description") or ""
        lines.append(f"{name} ({kind}) :: {label} - {desc}")

        if kind == "scalar_group":
            for fname, fmeta in (section.get("fields") or {}).items():
                lines.append(field_line(fname, fmeta))
        elif kind == "table":
            lines.append("  columns:")
            for cname, cmeta in (section.get("columns") or {}).items():
                lines.append(field_line(cname, cmeta))
            if section.get("canonical_items"):
                items = ", ".join(section["canonical_items"].keys())
                lines.append(f"  canonical items: {items}")
        lines.append("")  # spacer
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _base_mapping_prompt() -> str:
    try:
        return MAPPING_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "You map extracted values into the canonical schema. Follow the provided schema exactly."
        )


def _flatten_source(source: Any, prefix: str = "", max_items: int = 400) -> List[Dict[str, Any]]:
    """Produce a path → value listing to give the LLM stable handles.

    We cap the number of items to keep the prompt bounded.
    """
    flat: List[Dict[str, Any]] = []

    def _walk(value: Any, path: List[str]) -> None:
        if len(flat) >= max_items:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                _walk(v, path + [str(k)])
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                _walk(item, path + [str(idx)])
        else:
            flat.append({"path": ".".join(path), "value": value})

    _walk(source, path=prefix.split(".") if prefix else [])

    if len(flat) > max_items:
        return flat[:max_items] + [{"path": "...", "value": f"(truncated after {max_items} items)"}]
    return flat


def _build_prompt(source_json: Dict[str, Any]) -> str:
    summary = _schema_summary()
    source_pretty = json.dumps(source_json, indent=2, ensure_ascii=False)
    flattened = json.dumps(_flatten_source(source_json), indent=2, ensure_ascii=False)
    base = _base_mapping_prompt()

    table_sections = [name for name, spec in _schema_sections().items() if spec.get("kind") == "table"]
    scalar_sections = [name for name, spec in _schema_sections().items() if spec.get("kind") == "scalar_group"]

    return (
        f"{base}\n\n"
        f"Canonical Schema Definition:\n{summary}\n\n"
        f"Source JSON (as provided):\n{source_pretty}\n\n"
        f"Flattened source (path => value):\n{flattened}\n\n"
        "Output format (STRICT):\n"
        "{\n"
        '  "mapped": { <section_name>: <dict or array depending on section>, ... },\n'
        '  "missing_fields": [ { "table": "...", "field": "...", "reason": "...", "confidence": "...", "source_fields": ["..."] } ],\n'
        '  "metadata": { "warnings": [], "model_version": "<string>" }\n'
        "}\n\n"
        f"- Scalar groups ({', '.join(scalar_sections)}): return an object with every canonical field present (use null for missing).\n"
        f"- Tables ({', '.join(table_sections)}): return an array of row objects keyed by canonical column names; include only rows you can confidently map. If unknown, use an empty array.\n"
        "- Do NOT invent data; prefer null/empty when unsure. Preserve units (%, x, $) as shown in the source when copying values.\n"
    )


def _ensure_canonical_shape(mapped: Dict[str, Any]) -> Dict[str, Any]:
    canonical: Dict[str, Any] = {}
    sections = _schema_sections()
    for name, section in sections.items():
        kind = section.get("kind")
        value = mapped.get(name) if isinstance(mapped, dict) else None

        if kind == "scalar_group":
            field_defs = section.get("fields") or {}
            source_fields = value if isinstance(value, dict) else {}
            canonical[name] = {}
            for fname in field_defs.keys():
                canonical[name][fname] = source_fields.get(fname)
        elif kind == "table":
            # Expect an array of row objects; keep as-is, or coerce None to [].
            if value is None:
                canonical[name] = []
            elif isinstance(value, list):
                canonical[name] = value
            else:
                canonical[name] = value
        else:
            canonical[name] = value
    return canonical


def _normalize_missing_fields(
    missing_fields: List[MissingField], canonical: Dict[str, Any]
) -> List[MissingField]:
    """Only enforce missing fields for scalar groups (tables are variable-row)."""
    table_labels = _table_labels()
    field_labels = _field_labels()
    sections = _schema_sections()

    normalized: List[MissingField] = []
    seen: set[tuple[str, str]] = set()

    for item in missing_fields or []:
        if item.table not in canonical:
            continue
        section_kind = sections.get(item.table, {}).get("kind")
        if section_kind == "table":
            # Skip row-level enforcement for tables here.
            normalized.append(item)
            seen.add((item.table, item.field))
            continue
        if field_labels.get(item.table) and item.field not in field_labels[item.table]:
            continue
        item.table_label = item.table_label or table_labels.get(item.table)
        item.field_label = item.field_label or field_labels.get(item.table, {}).get(item.field)
        normalized.append(item)
        seen.add((item.table, item.field))

    for table, value in canonical.items():
        section_kind = sections.get(table, {}).get("kind")
        if section_kind != "scalar_group":
            continue
        labels = field_labels.get(table, {})
        for field_name, field_value in (value or {}).items():
            if (table, field_name) in seen:
                continue
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
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
    canonical = _ensure_canonical_shape(result.mapped or {})
    missing = _normalize_missing_fields(result.missing_fields or [], canonical)
    metadata = result.metadata or MappingMetadata()
    metadata.generated_at = datetime.utcnow()
    metadata.model_version = metadata.model_version or _schema_version()
    metadata.table_labels = dict(_table_labels())
    metadata.field_labels = {table: dict(fields) for table, fields in _field_labels().items()}
    return MappingResult(mapped=canonical, missing_fields=missing, metadata=metadata)


def _json_safe(text: str) -> Dict[str, Any]:
    """Parse JSON from model content with fallbacks for empty/garbage."""

    def try_parse(payload: str) -> Dict[str, Any] | None:
        try:
            return json.loads(payload)
        except Exception:
            return None

    cleaned = (text or "").strip()
    if not cleaned:
        return {}

    parsed = try_parse(cleaned)
    if parsed is not None:
        return parsed

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        parsed = try_parse(candidate)
        if parsed is not None:
            return parsed

    return {}


def _count_prompt_tokens(text: str) -> int | None:
    """Best-effort prompt token count to debug latency/size."""
    if not tiktoken:
        return None
    try:
        try:
            enc = tiktoken.encoding_for_model(settings.model_name)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except Exception:
        return None


def map_to_canonical(source_json: Dict[str, Any]) -> MappingResult:
    if not source_json:
        raise ValueError("Source JSON is empty; cannot perform mapping.")

    prompt = _build_prompt(source_json)
    tokens = _count_prompt_tokens(prompt)
    if tokens is not None:
        logger.info("mapping prompt tokens=%s model=%s", tokens, settings.model_name)
    else:
        logger.info("mapping prompt tokens=unknown (tiktoken unavailable) model=%s", settings.model_name)
    start = datetime.now(timezone.utc)
    client = OpenAI(
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        default_headers=settings.model_extra_headers,
    )
    response = client.chat.completions.create(
        model=settings.model_name,
        temperature=0.0,
        #response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You output canonical JSON mappings only. Follow instructions exactly.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info("mapping completion latency_ms=%.0f model=%s", duration_ms, settings.model_name)
    content = response.choices[0].message.content if response.choices else "{}"
    payload = _json_safe(content or "{}")
    if not payload:
        snippet = (content or "")[:400]
        raise ValueError(f"Model returned no parsable JSON for mapping. Raw output (truncated): {snippet}")

    try:
        parsed = MappingResult.model_validate(payload)
    except ValidationError:
        # As final fallback, try model_validate_json on raw content to surface a better message
        parsed = MappingResult.model_validate_json(content or "{}")

    return _finalize_mapping(parsed)


def normalize_mapping(mapping: MappingResult) -> MappingResult:
    """Normalize a mapping payload from the client before persisting."""
    return _finalize_mapping(mapping)
