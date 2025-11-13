from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

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


def _build_prompt(base_prompt: str, document_text: str) -> str:
    return f"{base_prompt}\n\n---\n\nDOCUMENT TEXT:\n\n{document_text}\n\n---\n\nReturn strict JSON only."


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


def _json_safe(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        # try to find JSON substring
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
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
    text = _read_pdf_text(pdf_path)
    prompt = _build_prompt(base_prompt, text)

    client = OpenAI(api_key=settings.model_api_key, base_url=settings.openai_base_url)

    resp = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": "You are a precise data extraction engine. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    content = resp.choices[0].message.content if resp.choices else "{}"
    data = _json_safe(content or "{}")
    confidences = _compute_confidences(data)
    inferred_tables = [k for k in data.keys()]
    warnings: List[str] = []
    snippets = _find_snippets(data, text)

    return ExtractionResult(
        extracted_json=data,
        confidences=confidences,
        inferred_tables=inferred_tables,
        warnings=warnings,
        text_snippets=snippets,
    )

