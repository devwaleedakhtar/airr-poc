from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import re

from openai import OpenAI
from pypdf import PdfReader

from ..core.config import settings


@dataclass
class ExtractionResult:
    extracted_json: Dict[str, Any]
    confidences: Dict[str, Any] | None
    inferred_tables: List[str] | None
    warnings: List[str] | None
    text_snippets: Dict[str, str] | None


def _read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(texts)


def _load_base_prompt() -> str:
    try:
        with open("backend/app/prompts/extraction_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            "Extract tables and key-value pairs from the text. Group related fields into logical table names. "
            "If a header is not found, infer a logical table name based on field names. Return a JSON object where "
            "each key is the table name and value is an object of key/value pairs."
        )


def _strip_code_fences(text: str) -> str:
    """Remove common markdown code fences (``` or ```json) if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def _fix_thousands_separators(candidate: str) -> str:
    """Wrap bare numbers with thousands separators in quotes to make them JSON-safe.

    Example: `"Net Rentals SF": 111,625,` -> `"Net Rentals SF": "111,625",`.
    """

    pattern = re.compile(r'(:\s*)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(\s*[,\}])')

    def _repl(match: re.Match[str]) -> str:
        prefix, number, suffix = match.groups()
        return f'{prefix}"{number}"{suffix}'

    return pattern.sub(_repl, candidate)


def _json_safe(text: str) -> Dict[str, Any]:
    def try_parse(payload: str) -> Dict[str, Any] | None:
        try:
            return json.loads(payload)
        except Exception:
            return None

    # First, strip any markdown fences the model may have added.
    cleaned = _strip_code_fences(text or "")

    # Try parsing the whole payload.
    parsed = try_parse(cleaned)
    if parsed is not None:
        return parsed

    # Fallback: find the first {...} block and try to parse that.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = cleaned[start : end + 1]

    parsed = try_parse(candidate)
    if parsed is not None:
        return parsed

    # Last-resort fix: wrap thousands-separated numbers (e.g., 111,625) in quotes.
    fixed = _fix_thousands_separators(candidate)
    parsed = try_parse(fixed)
    if parsed is not None:
        return parsed

    return {}


def _compute_confidences(data: Dict[str, Any]) -> Dict[str, Any]:
    # Simple heuristic confidences by presence
    result: Dict[str, Any] = {}
    for table, kv in data.items():
        if not isinstance(kv, dict):
            continue
        result[table] = {k: ("high" if (v is not None and str(v).strip()) else "low") for k, v in kv.items()}
    return result


def _find_snippets(data: Dict[str, Any], full_text: str, window: int = 80) -> Dict[str, str]:
    snippets: Dict[str, str] = {}
    lower_text = full_text.lower()
    for table, kv in data.items():
        if not isinstance(kv, dict):
            continue
        for key, value in kv.items():
            value_str = str(value) if value is not None else ""
            field_label = f"{table}.{key}"
            idx = lower_text.find(value_str.lower()) if value_str else -1
            if idx != -1:
                start = max(0, idx - window)
                end = min(len(full_text), idx + len(value_str) + window)
                snippets[field_label] = full_text[start:end]
            else:
                # fallback to key search
                kidx = lower_text.find(str(key).lower())
                if kidx != -1:
                    start = max(0, kidx - window)
                    end = min(len(full_text), kidx + len(str(key)) + window)
                    snippets[field_label] = full_text[start:end]
    return snippets


def extract_from_pdf(pdf_path: str) -> ExtractionResult:
    base_prompt = _load_base_prompt()
    full_text = _read_pdf_text(pdf_path)
    # If the PDF has no extractable text at all, fail fast so the client
    # sees a clear error instead of an empty extraction.
    if not full_text.strip():
        raise RuntimeError(
            "PDF contains no extractable text; ensure the sheet exports as a text-based PDF (not an image-only scan)."
        )

    client = OpenAI(api_key=settings.model_api_key)

    with open(pdf_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="assistants")

    system_prompt = "You are a precise data extraction engine.\n\n" + base_prompt

    response = client.responses.create(
        model=settings.model_name,
        input=[
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": system_prompt},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": uploaded.id},
                ],
            },
        ],
        temperature=0.0,
    )

    try:
        output = response.output[0].content[0].text if response.output else "{}"
    finally:
        try:
            client.files.delete(uploaded.id)
        except Exception:
            pass

    data = _json_safe(output or "{}")
    # Treat a completely empty/invalid JSON result as an error so the caller
    # surfaces a useful message instead of silently returning no data.
    if not data:
        snippet = (output or "")[:400]
        raise RuntimeError(
            f"Model returned no parsable JSON for this PDF. Raw output (truncated): {snippet}"
        )

    confidences = _compute_confidences(data)
    inferred_tables = [k for k in data.keys()]
    warnings: List[str] = []
    snippets = _find_snippets(data, full_text)

    return ExtractionResult(
        extracted_json=data,
        confidences=confidences,
        inferred_tables=inferred_tables,
        warnings=warnings,
        text_snippets=snippets,
    )
