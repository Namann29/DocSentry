from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from ..errors import ProcessingError
from .base import ExtractionAdapter, PageText, Word, group_lines


class PyMuPDFAdapter(ExtractionAdapter):
    """Rung 1: native PDF text with word-level bounding boxes. Also opens PNG/JPEG
    (yielding pages with no words, flagged needs_ocr)."""
    name = "native_pdf"

    def extract(self, path: Path) -> Iterator[PageText]:
        try:
            doc = fitz.open(str(path))
        except Exception as e:  # fitz raises generic errors for broken files
            raise ProcessingError(f"Cannot open document: {type(e).__name__}") from e
        with doc:
            if doc.needs_pass:
                raise ProcessingError("Document is password-protected; supply the password at upload")
            for i, page in enumerate(doc, start=1):
                raw = page.get_text("words")
                words = [Word(w[4].strip(), float(w[0]), float(w[1]), float(w[2]), float(w[3]), i, 0.99)
                         for w in raw if w[4].strip()]
                yield PageText(i, page.rect.width, page.rect.height, words, group_lines(words, i),
                               self.name if words else "needs_ocr")


def render_page_png(path: Path, page_no: int, zoom: float = 1.5) -> bytes:
    with fitz.open(str(path)) as doc:
        if page_no < 1 or page_no > doc.page_count:
            raise ProcessingError("Page out of range")
        pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")


def pdf_info(path: Path) -> dict[str, Any]:
    with fitz.open(str(path)) as doc:
        return {"page_count": doc.page_count, "encrypted": bool(doc.needs_pass),
                "metadata": {k: v for k, v in (doc.metadata or {}).items() if v}}