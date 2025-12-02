from __future__ import annotations

from typing import Dict, List

from . import graph_client
from .o365_converter_service import ensure_graph_item_id
from .extractor_service import ExtractionResult, extract_from_text


def _grid_to_text(grid: List[List[str]]) -> str:
    lines: List[str] = []
    for row in grid:
        cells = [(cell or "").strip() for cell in row]
        while cells and cells[0] == "":
            cells.pop(0)
        while cells and cells[-1] == "":
            cells.pop()
        if not cells:
            lines.append("")
            continue
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_via_office365(doc: Dict[str, object], workbook_id: str, sheet_name: str) -> ExtractionResult:
    graph_item_id = ensure_graph_item_id(doc, workbook_id)

    session_id = graph_client.create_workbook_session(graph_item_id)
    grid = graph_client.get_used_range_text(graph_item_id, session_id, sheet_name)
    sheet_text = _grid_to_text(grid)

    return extract_from_text(
        sheet_text,
        empty_error_msg=(
            "Sheet contains no extractable text; ensure the sheet has at least some non-empty cells."
        ),
    )

