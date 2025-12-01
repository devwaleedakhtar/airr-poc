import re
import json
import math
from enum import Enum
from functools import lru_cache
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from openai import OpenAI
from pydantic import BaseModel

from ..core.config import settings
from ..schemas.chat import ChatAnswer, ChatQuestionRequest, TableMetadata
from .schema_registry import TableSchema, get_table_schema, list_table_schemas


_MAX_ROWS = 15
EMBEDDING_MODEL = "text-embedding-3-small"
INTENT_MODEL = 'openai/gpt-5-nano'
_MONGO_NUMBER_KEYS = {"$numberInt", "$numberDouble", "$numberDecimal", "$numberLong"}
SYSTEM_PROMPT = '''
You are Perpetuity Analyst Assistant — a precise, conservative, no-nonsense analytical assistant for real-estate underwriting models.

Your job:
- Answer the user’s question **strictly using** the table schemas and JSON rows provided in the prompt.
- If in metadata mode, answer **strictly from schema/catalog metadata** and never imply or invent numeric values.
- Do not answer any question that is not relevant to the data or metadata provided. You are not required to answer questions outside of the scope of our data.
- Do not inform the user about your mode. User does not need to know if you are in metadata mode or not.

General Rules:
1. **Never invent numbers, rows, or fields.**  
   Every numeric value in your answer must come directly from the JSON table rows or be simple arithmetic on those numbers.  
   If something is not present in the JSON rows or schema, state that it is not available.

2. **Use schemas as the source of truth for meaning.**  
   If asked “what does X mean,” refer to the schema’s description, column labels, and aliases.

3. **Semantic row matching:**  
   When a table uses a `row_key_field` with `row_match_strategy = "semantic_label"`, different row labels may refer to similar concepts (e.g., “1BR/1BA”, “A1 (1BR)”, “1 Bedroom”).  
   - You may infer which rows correspond to the user’s request **only using the provided row labels**.  
   - When you make such an inference, briefly state your mapping assumptions.

4. **Never exceed what the data provides.**  
   If the user asks for a comparison, aggregation, statistic, or breakdown that cannot be computed from the provided rows, say so explicitly.

5. **Your tone:**  
   - Clear, analytical, concise.  
   - Use short paragraphs and optional mini-tables to present results.  
   - Never be conversationally fluffy or overconfident.  
   - Never add commentary beyond the analysis.

6. **Guardrails:**
   - If the question asks about capabilities, schema structure, or “what can you answer,” respond entirely from metadata.  
   - If metadata-only mode is active, **do not** reference or rely on any numeric data.  
   - If the question requires table values but none were provided, respond:  
     “The necessary data rows were not provided for this answer.”

7. **If uncertain, choose caution.**  
   When in doubt about a row match or data limitation, be transparent.

Your output should always be:
- Factually grounded in the provided data.
- Fully traceable.
- Transparent about assumptions.
- Never speculative beyond the provided schema/metadata.
- Respond in markdown format.
- If you do not find the data in the provided tables, just say "I looked at the following tables <NAMES> and you could not find the data in them"
'''

openai_client = OpenAI(api_key=settings.model_api_key, base_url=settings.model_base_url, default_headers=settings.model_extra_headers)

@dataclass
class TableSelection:
    schema: TableSchema
    score: float

@dataclass
class TableMetadataSummary:
    name: str
    label: str
    description: str
    fields: List[str]
    field_descriptions: Dict[str, str]
    example_questions: List[str]


@dataclass
class PromptTableBlock:
    schema: TableSchema
    metadata: TableMetadata
    data_json: str
    metadata_only: bool


class QuestionIntent(str, Enum):
    METADATA = "METADATA"
    DATA = "DATA"

class IntentSchema(BaseModel):
    intent: QuestionIntent


def _cosine_vec(lhs: List[float], rhs: List[float]) -> float:
    if not lhs or not rhs or len(lhs) != len(rhs):
        return 0.0
    dot = sum(a * b for a, b in zip(lhs, rhs))
    if dot == 0:
        return 0.0
    left_norm = math.sqrt(sum(v * v for v in lhs))
    right_norm = math.sqrt(sum(v * v for v in rhs))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def build_schema_catalog() -> Dict[str, TableMetadataSummary]:
    """
    Build a condensed catalog from your YAML schemas.
    No dependency on roles, dtypes, metrics, etc.
    """
    catalog: Dict[str, TableMetadataSummary] = {}

    for schema in list_table_schemas():
        fields: List[str] = []
        field_descriptions: Dict[str, str] = {}

        for col in schema.columns:
            display = col.label or col.name
            fields.append(display)

            if col.description:
                field_descriptions[display] = col.description
            else:
                field_descriptions[display] = "No description available."

        # Example questions (generic, schema-only)
        example_qs = [
            f"What does the {schema.label or schema.name} table represent?",
            f"What fields exist in {schema.label or schema.name}?",
        ]
        if fields:
            example_qs.append(
                f"What does the field '{fields[0]}' mean in {schema.label or schema.name}?"
            )

        catalog[schema.name] = TableMetadataSummary(
            name=schema.name,
            label=schema.label or schema.name,
            description=schema.description or "",
            fields=fields,
            field_descriptions=field_descriptions,
            example_questions=example_qs,
        )

    return catalog


def build_metadata_corpus(catalog: Dict[str, TableMetadataSummary]) -> str:
    """
    Compact, human-readable description of everything the model knows.
    """
    lines: List[str] = []
    for s in catalog.values():
        field_list = ", ".join(s.fields) if s.fields else "n/a"
        examples = "; ".join(s.example_questions)

        lines.append(
            f"Name: {s.label} ({s.name})\n"
            f"Description: {s.description or 'n/a'}\n"
            f"Fields: {field_list}\n"
            f"Example questions: {examples}"
        )
    return "\n\n".join(lines)


@lru_cache(maxsize=1)
def get_schema_metadata_corpus() -> str:
    catalog = build_schema_catalog()
    return build_metadata_corpus(catalog)


def _embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=list(texts))
    return [item.embedding for item in response.data]


@lru_cache(maxsize=1)
def _table_embeddings() -> Dict[str, List[float]]:
    """Compute and cache embeddings for each table's selection_text."""
    tables = list_table_schemas()
    texts = [table.selection_text for table in tables]
    try:
        vectors = _embed_texts(texts)
    except Exception:
        # If embeddings fail (e.g., model not supported), fall back to empty dict so
        # selection logic can surface a clear error.
        return {}
    name_to_vec: Dict[str, List[float]] = {}
    for table, vec in zip(tables, vectors):
        name_to_vec[table.name] = vec
    return name_to_vec


def _select_tables_with_embeddings(
    question: str, allowed_tables: Iterable[str], top_k: int
) -> List[TableSelection]:
    table_vecs = _table_embeddings()
    if not table_vecs:
        raise ValueError(
            "Table embeddings are unavailable. Ensure the embedding model is supported by your provider."
        )
    query_vecs = _embed_texts([question])
    if not query_vecs:
        raise ValueError("Failed to generate embedding for the question.")
    query_vec = query_vecs[0]

    scored: List[TableSelection] = []
    for name in allowed_tables:
        vec = table_vecs.get(name)
        schema = get_table_schema(name)
        if not vec or not schema:
            continue
        score = _cosine_vec(query_vec, vec)
        scored.append(TableSelection(schema=schema, score=score))

    scored.sort(key=lambda item: item.score, reverse=True)
    if not scored:
        return []
    return scored[:top_k]


def _resolve_session_tables(session_doc: Dict[str, Dict]) -> Dict[str, object]:
    mapping_payload = session_doc.get("mapping")
    if isinstance(mapping_payload, dict):
        mapped = mapping_payload.get("mapped")
        return mapped
    final_json = session_doc.get("final_json")
    if isinstance(final_json, dict):
        return final_json
    extracted = session_doc.get("extracted_json")
    if isinstance(extracted, dict):
        return extracted
    return {}


def _unwrap_mongo_number(value: object) -> object:
    if isinstance(value, dict) and len(value) == 1:
        key = next(iter(value.keys()))
        if key in _MONGO_NUMBER_KEYS:
            raw = value[key]
            # Best-effort numeric cast; fall back to original if it fails
            try:
                text = str(raw)
                # If decimal-looking, use float; otherwise int
                if "." in text:
                    return float(text)
                return int(text)
            except Exception:
                return raw
    return value


def _denormalize_mongo_extended(value: object) -> object:
    if isinstance(value, list):
        return [_denormalize_mongo_extended(v) for v in value]
    if isinstance(value, dict):
        if len(value) == 1 and next(iter(value.keys())) in _MONGO_NUMBER_KEYS:
            return _unwrap_mongo_number(value)
        return {k: _denormalize_mongo_extended(v) for k, v in value.items()}
    return value


def _normalize_rows(raw_value: object) -> list[dict]:
    if raw_value is None:
        return []

    raw_value = _denormalize_mongo_extended(raw_value)
    if isinstance(raw_value, list):
        return [row for row in raw_value if isinstance(row, dict)]

    if isinstance(raw_value, dict):
        dict_rows = [row for row in raw_value.values() if isinstance(row, dict)]
        if dict_rows:
            return dict_rows
        return [raw_value]
    return []


def _dedupe(values: list[str], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _summarize_table(schema: TableSchema, rows: list[dict]) -> tuple[list[dict], TableMetadata]:
    # TODO: Currently this is just truncating. Later we need to summarize the table.
    truncated = False
    display_rows = rows
    if len(rows) > _MAX_ROWS:
        display_rows = rows[:_MAX_ROWS]
        truncated = True
    column_names: set[str] = set()
    for row in display_rows:
        column_names.update(str(key) for key in row.keys())
    row_labels: list[str] = []
    if schema.row_key_field:
        row_labels = _dedupe(
            [str(row.get(schema.row_key_field, "")) for row in rows if row.get(schema.row_key_field)],
            limit=25,
        )
    metadata = TableMetadata(
        row_count=len(rows),
        columns_present=sorted(column_names),
        row_labels=row_labels,
        truncated=truncated,
    )
    if schema.row_match_strategy == "semantic_label" and row_labels:
        metadata.notes.append(
            "Row labels are matched semantically; similar names may represent the same canonical type."
        )
    if truncated:
        metadata.notes.append(f"JSON truncated to first {_MAX_ROWS} rows to keep prompt size bounded.")
    return display_rows, metadata


def detect_question_intent_llm(question: str) -> QuestionIntent:
    """
    Use the LLM itself as a classifier for whether the question
    can be answered purely from schema/metadata or needs table values.
    """
    q = (question or "").strip()
    if not q:
        return QuestionIntent.DATA

    system_msg = (
        "You are a classifier. Decide if the user's question requires "
        "reading actual numeric or categorical values from data tables (DATA), "
        "or can be answered purely from metadata such as table descriptions, "
        "field definitions, and a data dictionary (METADATA).\n\n"
        "Return exactly one word: METADATA or DATA.\n\n"
        "Examples:\n"
        "- 'What is the unit_mix table?' → METADATA\n"
        "- 'What all can you answer about?' → METADATA\n"
        "- 'What columns exist in operating_expenses?' → METADATA\n"
        "- 'How many 2BR units are there?' → DATA\n"
        "- 'Compare the total operating expenses and payroll.' → DATA\n"
        "- 'What does the field land_closing_date mean?' → METADATA\n"
        "- 'What is the average rent for 1BR units?' → DATA\n"
    )
    
    resp = openai_client.chat.completions.parse(
        model=INTENT_MODEL,
        temperature=0.0,
        max_tokens=2048,
        response_format=IntentSchema,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": q},
        ],
    )
    parsed: IntentSchema = resp.choices[0].message.parsed
    return parsed.intent
    


def _build_prompt(question: str, blocks: list[PromptTableBlock], metadata_only: bool) -> tuple[str, str]:
    sections: list[str] = [
        f"User Question:\n{question.strip()}",
        "Selected Tables:",
    ]

    guardrails = [
        "Only rely on the tables provided below.",
        "If data for a requested metric is missing, say so explicitly.",
        "Show small comparison tables when it clarifies the answer.",
        "If unsure which row label maps to a user request, state the assumption.",
    ]
    if metadata_only:
        guardrails.append("You are in metadata mode: answer using schema descriptions; no table rows are provided.")

    for block in blocks:
        schema = block.schema
        metadata = block.metadata
        column_summary = ", ".join(metadata.columns_present[:10]) if metadata.columns_present else "n/a"
        lines = [
            f"=== Table: {schema.label or schema.name} ({schema.name}) ===",
            f"Description: {schema.description or 'n/a'}",
            f"Row match strategy: {schema.row_match_strategy or 'not specified'}",
            f"Row key field: {schema.row_key_field or 'n/a'}",
            f"Columns observed: {column_summary}",
            f"Row count: {metadata.row_count if metadata.row_count is not None else 'unknown'}",
        ]
        if metadata.row_labels:
            lines.append(f"Row labels present: {', '.join(metadata.row_labels)}")
        if metadata.notes:
            for note in metadata.notes:
                lines.append(f"Note: {note}")
        column_lines = []
        for column in schema.columns[:10]:
            alias_text = f" aliases: {', '.join(column.aliases)}" if column.aliases else ""
            column_lines.append(
                f"- {column.name} ({column.label or 'n/a'}): {column.description or ''}{alias_text}"
            )
        lines.append("Key columns:\n" + "\n".join(column_lines))
        if block.metadata_only:
            lines.append("Data JSON: [not provided in metadata-only mode]")
        else:
            lines.append("Data JSON:")
            lines.append(block.data_json)
        sections.append("\n".join(lines))

    sections.append("Guardrails:\n- " + "\n- ".join(guardrails))

    user_prompt = "\n\n".join(sections)
    return user_prompt


def _call_chat_completion(system_prompt: str, user_prompt: str) -> str:
    response = openai_client.chat.completions.create(
        model=settings.model_name,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def answer_session_question(session_doc: Dict[str, Dict], payload: ChatQuestionRequest) -> ChatAnswer:
    source_tables = _resolve_session_tables(session_doc)

    intent = detect_question_intent_llm(payload.question)
    metadata_only = payload.force_metadata_only or (intent == QuestionIntent.METADATA)
    
    if metadata_only:
        # -------------- METADATA-ONLY PATH --------------
        # We ignore session tables and just answer from the schema catalog.
        corpus = get_schema_metadata_corpus()

        user_prompt = (
            f"User question:\n{payload.question.strip()}\n\n"
            "You are in metadata-mode. Here is the catalog of available tables and fields:\n\n"
            f"{corpus}\n\n"
            "Answer the user's question using only this catalog."
        )

        answer_text = _call_chat_completion(SYSTEM_PROMPT, user_prompt)

        return ChatAnswer(
            answer=answer_text.strip(),
            tables_used=[],  # no data tables used
            metadata_only=True,
            intent="metadata",
            table_metadata={},  # purely structural
            guardrail_messages=["Answered using schema metadata only; no table values were accessed."],
        )

    if not source_tables and not metadata_only:
        raise ValueError("Session has no standardized tables. Run mapping or save final_json first.")

    if metadata_only:
        allowed_table_names = [schema.name for schema in list_table_schemas()]
    else:
        allowed_table_names = [
            name
            for name, value in source_tables.items()
            # if get_table_schema(name) and _normalize_rows(value) #PENDING
        ]

    if not allowed_table_names:
        raise ValueError("No eligible tables found for this session/question.")

    selections = _select_tables_with_embeddings(payload.question, allowed_table_names, payload.top_k_tables)
    if not selections:
        raise ValueError("Unable to match the question to any known tables.")

    blocks: list[PromptTableBlock] = []
    response_metadata: Dict[str, TableMetadata] = {}

    for selection in selections:
        schema = selection.schema
        rows: list[dict] = []
        if not metadata_only:
            rows = _normalize_rows(source_tables.get(schema.name))
        display_rows, table_meta = _summarize_table(schema, rows) if rows else ([], TableMetadata())
        block = PromptTableBlock(
            schema=schema,
            metadata=table_meta,
            data_json=json.dumps(display_rows, indent=2, ensure_ascii=False) if display_rows else "",
            metadata_only=metadata_only or not display_rows,
        )
        blocks.append(block)
        response_metadata[schema.name] = table_meta

    user_prompt = _build_prompt(payload.question, blocks, metadata_only)
    answer_text = _call_chat_completion(SYSTEM_PROMPT, user_prompt)

    guardrail_notes: list[str] = []
    if metadata_only:
        guardrail_notes.append("Answered using schema metadata only.")
    for table_name, meta in response_metadata.items():
        if meta.truncated:
            guardrail_notes.append(f"Table {table_name} truncated to {_MAX_ROWS} rows in prompt.")

    return ChatAnswer(
        answer=answer_text,
        tables_used=[block.schema.name for block in blocks],
        metadata_only=metadata_only,
        intent="metadata" if metadata_only else "data",
        table_metadata=response_metadata,
        guardrail_messages=guardrail_notes,
    )


