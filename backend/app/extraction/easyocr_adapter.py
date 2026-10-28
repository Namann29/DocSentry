"""EasyOCR rung: deep-learning text detection (CRAFT) and recognition (CRNN)."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fitz

from ..config import settings
from ..errors import ProcessingError
from .base import ExtractionAdapter, PageText, Word, group_lines
from .ocr_adapter import quality_gate, render_page

_reader: Any = None


def easyocr_available() -> bool:
    try:
        import easyocr  # noqa: F401
        return True
    except Exception:
        return False


def reader() -> Any:
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader([l.strip() for l in settings.easyocr_langs.split(",") if l.strip()], gpu=False, verbose=False)
    return _reader


def split_words(box: Any, text: str, conf: float, scale: float, page: int) -> list[Word]:
    """Split a line-level OCR result into word tokens with proportional boxes (page points)."""
    parts = str(text).split()
    if not parts:
        return []
    xs, ys = [p[0] for p in box], [p[1] for p in box]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    nchars = sum(len(p) for p in parts) + max(0, len(parts) - 1)
    cw = (x1 - x0) / max(nchars, 1)
    out: list[Word] = []
    cursor = x0
    for p in parts:
        w = cw * len(p)
        out.append(Word(p, cursor * scale, y0 * scale, (cursor + w) * scale, y1 * scale, page, round(float(conf), 3)))
        cursor += w + cw
    return out


class EasyOCRAdapter(ExtractionAdapter):
    name = "ocr_easyocr"

    def extract(self, path: Path) -> Iterator[PageText]:
        import cv2
        try:
            doc = fitz.open(str(path))
        except Exception as e:
            raise ProcessingError(f"Cannot open document: {type(e).__name__}") from e
        rd = reader()
        with doc:
            for i, page in enumerate(doc, start=1):
                bgr = render_page(page)
                quality = quality_gate(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
                results = rd.readtext(bgr, detail=1, paragraph=False, canvas_size=1600, mag_ratio=1.0)
                scale = page.rect.width / bgr.shape[1]
                words: list[Word] = []
                for box, text, conf in results:
                    words.extend(split_words(box, text, conf, scale, i))
                pt = PageText(i, page.rect.width, page.rect.height, words, group_lines(words, i), self.name if words else "needs_ocr")
                quality["engine"] = self.name
                quality["ocr_mean_confidence"] = round(sum(w.conf for w in words) / len(words), 3) if words else 0.0
                pt.quality = quality
                yield pt