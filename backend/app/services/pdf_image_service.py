from __future__ import annotations

import os
import tempfile

import fitz  # type: ignore[import-untyped]


def pdf_to_image(pdf_path: str, zoom: float = 4.2) -> str:
    """Render the first page of a PDF as a high-resolution PNG image.

    Returns the path to a temporary PNG file. Caller is responsible for cleanup.
    """
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(0)
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        pix.save(tmp_path)
        return tmp_path
    finally:
        doc.close()
