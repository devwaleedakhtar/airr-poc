from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Dict, Optional

from cloudinary.utils import private_download_url

from ..core.cloudinary import download_to_temp
from ..services import graph_client


@dataclass
class ConversionResult:
    pdf_path: str
    graph_item_id: Optional[str] = None


def _download_original_to_temp(doc: Dict[str, object]) -> str:
    filename = str(doc.get("filename") or "workbook.xlsx")
    original_public_id = doc.get("original_public_id")
    original_format = str(doc.get("original_format") or os.path.splitext(filename)[1].lstrip(".")) or "xlsx"

    if original_public_id:
        signed = private_download_url(
            str(original_public_id),
            original_format,
            resource_type="raw",
            type="private",
        )
        return download_to_temp(signed, suffix=f".{original_format}")

    original_url = doc.get("original_url")
    if not isinstance(original_url, str) or not original_url:
        raise RuntimeError("Workbook document is missing original_url for Office365 conversion")
    suffix = os.path.splitext(filename)[1] or ".xlsx"
    return download_to_temp(original_url, suffix=suffix)


def ensure_graph_item_id(doc: Dict[str, object], workbook_id: str) -> str:
    """Ensure the workbook exists as a Graph drive item and return its id."""
    graph_item_id: Optional[str] = None
    raw_item = doc.get("graph_item_id")
    if isinstance(raw_item, str) and raw_item:
        graph_item_id = raw_item

    # If we do not yet have a Graph item, upload the original workbook now.
    if not graph_item_id:
        tmp_path = _download_original_to_temp(doc)
        try:
            with open(tmp_path, "rb") as f:
                content = f.read()
            graph_item_id = graph_client.upload_workbook(workbook_id, str(doc.get("filename") or "workbook.xlsx"), content)
            # NOTE: we could persist graph_item_id back into Mongo here via a repo helper
            # to avoid re-uploading the same workbook in future operations.
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except FileNotFoundError:
                    pass

    if not graph_item_id:
        raise RuntimeError("Failed to obtain Graph drive item id for workbook")

    return graph_item_id


def convert_via_office365(doc: Dict[str, object], workbook_id: str, sheet_name: str) -> ConversionResult:
    """Convert a single sheet to PDF via Excel Online (Microsoft Graph)."""
    graph_item_id = ensure_graph_item_id(doc, workbook_id)

    session_id = graph_client.create_workbook_session(graph_item_id)
    graph_client.activate_sheet(graph_item_id, session_id, sheet_name)
    graph_client.hide_other_sheets(graph_item_id, session_id, sheet_name)
    graph_client.auto_fit_columns(graph_item_id, session_id, sheet_name)
    graph_client.set_single_page_layout(graph_item_id, session_id, sheet_name)

    pdf_bytes = graph_client.download_pdf(graph_item_id, session_id)

    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    return ConversionResult(pdf_path=pdf_path, graph_item_id=graph_item_id)
