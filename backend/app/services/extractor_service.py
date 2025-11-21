from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

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


def _read_pdf_text(path: str, max_chars: int = 100_000) -> str:
    reader = PdfReader(path)
    texts: list[str] = []
    for page in reader.pages:
        try:
            if len(texts) >= max_chars:
                break
            texts.append(page.extract_text() or "")
        except Exception:
            pass
        if sum(len(t) for t in texts) >= max_chars:
            break
    # Truncate to max_chars to avoid oversized prompts.
    full = "\n".join(texts)
    if len(full) > max_chars:
        return full[:max_chars]
    return full


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


def _split_extraction_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    """Support both legacy shape and new shape with confidences."""
    if not isinstance(payload, dict):
        return {}, None
    if "extracted" in payload:
        return payload.get("extracted") or {}, payload.get("confidences") or payload.get("confidence") or None
    return payload, None


def _compute_confidences(data: Dict[str, Any]) -> Dict[str, Any]:
    # Heuristic confidences: start at "medium", downgrade blanks, upgrade simple numerics, flag out-of-range percents.
    result: Dict[str, Any] = {}

    def rate(value: Any) -> str:
        if value is None:
            return "low"
        text = str(value).strip()
        if text == "":
            return "low"
        percent_match = re.match(r"^-?\d+(\.\d+)?%$", text)
        if percent_match:
            try:
                num = float(text.rstrip("%"))
                if num < -5 or num > 150:
                    return "low"
            except Exception:
                return "low"
            return "medium"
        # numeric-ish tokens
        try:
            float(text.replace(",", ""))
            return "medium"
        except Exception:
            pass
        return "medium"

    for table, kv in data.items():
        if not isinstance(kv, dict):
            continue
        result[table] = {k: rate(v) for k, v in kv.items()}
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
    if not full_text.strip():
        raise RuntimeError(
            "PDF contains no extractable text; ensure the sheet exports as a text-based PDF (not an image-only scan)."
        )

    # Build chat messages with inlined PDF text. This works across OpenAI and OpenRouter.
    messages = [
        {
            "role": "system",
            "content": "You are a precise data extraction engine.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": base_prompt},
                {"type": "text", "text": "PDF TEXT:\n" + full_text},
            ],
        },
    ]

    client = OpenAI(api_key=settings.model_api_key, base_url=settings.model_base_url, default_headers=settings.model_extra_headers)
    response = client.chat.completions.create(
        model=settings.model_name,
        temperature=0.0,
        messages=messages,
    )

    output = response.choices[0].message.content if response.choices else "{}"

    payload = _json_safe(output or "{}")
    extracted_json, model_confidences = _split_extraction_payload(payload)
    if not extracted_json:
        snippet = (output or "")[:400]
        raise RuntimeError(
            f"Model returned no parsable JSON for this PDF. Raw output (truncated): {snippet}"
        )

    confidences = model_confidences if model_confidences else _compute_confidences(extracted_json)
    inferred_tables = [k for k in extracted_json.keys()]
    warnings: List[str] = []
    snippets = _find_snippets(extracted_json, full_text)

    return ExtractionResult(
        extracted_json=extracted_json,
        confidences=confidences,
        inferred_tables=inferred_tables,
        warnings=warnings,
        text_snippets=snippets,
    )
