"""Tesseract OCR rung and shared image helpers (render, quality gate, preprocessing)."""
from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fitz

from ..config import settings
from ..errors import ProcessingError
from .base import ExtractionAdapter, PageText, Word, group_lines

_DEFAULT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
RENDER_DPI = 300
MAX_SIDE = 1800
MIN_SIDE = 1000


def tesseract_cmd() -> str | None:
    for cand in (settings.tesseract_cmd, shutil.which("tesseract"), _DEFAULT_WIN):
        if cand and os.path.exists(cand):
            return cand
    return None


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except Exception:
        return False
    return tesseract_cmd() is not None


def render_page(page: Any) -> Any:
    """Page -> BGR image whose short side is at least MIN_SIDE and long side at most MAX_SIDE pixels."""
    import cv2
    import numpy as np
    zoom = RENDER_DPI / 72
    if max(page.rect.width, page.rect.height) * zoom > MAX_SIDE:
        zoom = MAX_SIDE / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if pix.n == 3 else cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
    if min(bgr.shape[:2]) < MIN_SIDE:
        f = MIN_SIDE / min(bgr.shape[:2])
        bgr = cv2.resize(bgr, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    return bgr


def quality_gate(gray: Any) -> dict[str, Any]:
    import cv2
    h, w = gray.shape[:2]
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    contrast = float(gray.std())
    brightness = float(gray.mean())
    warnings = []
    if blur < 60:
        warnings.append("Image is blurry (low Laplacian variance); re-scan at higher quality")
    if contrast < 35:
        warnings.append("Low contrast")
    if brightness < 70 or brightness > 215:
        warnings.append("Very dark or very bright image")
    return {"width": w, "height": h, "blur_variance": round(blur, 1), "contrast": round(contrast, 1),
            "brightness": round(brightness, 1), "warnings": warnings, "ok": not warnings}


def preprocess(gray: Any) -> tuple[Any, Any, float]:
    """Returns (enhanced grey, binary, deskew angle). Cheap operations only; this runs on every page."""
    import cv2
    import numpy as np
    g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    g = cv2.addWeighted(g, 1.5, cv2.GaussianBlur(g, (0, 0), 2), -0.5, 0)
    den = cv2.medianBlur(g, 3)
    thr = cv2.threshold(den, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    angle = 0.0
    if len(coords) > 500:
        a = cv2.minAreaRect(coords.astype(np.float32))[-1]
        a = a - 90 if a > 45 else a
        if abs(a) <= 5:
            angle = float(a)
    if abs(angle) > 0.3:
        h, w = gray.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        den = cv2.warpAffine(den, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        g = cv2.warpAffine(g, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    binary = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    return g, binary, angle


class TesseractOCRAdapter(ExtractionAdapter):
    name = "ocr_tesseract"

    def __init__(self, langs: str | None = None) -> None:
        self.langs = langs or settings.ocr_langs

    def extract(self, path: Path) -> Iterator[PageText]:
        import cv2
        import pytesseract
        cmd = tesseract_cmd()
        if not cmd:
            raise ProcessingError("Tesseract OCR is not installed")
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            doc = fitz.open(str(path))
        except Exception as e:
            raise ProcessingError(f"Cannot open document: {type(e).__name__}") from e
        with doc:
            for i, page in enumerate(doc, start=1):
                bgr = render_page(page)
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                quality = quality_gate(gray)
                enhanced, binary, angle = preprocess(gray)
                quality["deskew_degrees"] = round(angle, 2)
                best, best_score = None, -1.0
                for candidate, psm in ((enhanced, 6), (enhanced, 11), (binary, 6), (binary, 11)):
                    d = pytesseract.image_to_data(candidate, lang=self.langs, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
                    score = sum(float(c) for c, t in zip(d["conf"], d["text"]) if str(t).strip() and float(c) >= 0)
                    if score > best_score:
                        best, best_score = d, score
                data = best
                quality["engine"] = self.name
                quality["ocr_total_confidence"] = round(best_score, 1)
                scale = page.rect.width / gray.shape[1]
                words: list[Word] = []
                for t, c, x, y, w, h in zip(data["text"], data["conf"], data["left"], data["top"], data["width"], data["height"]):
                    t = (t or "").strip()
                    try:
                        conf = float(c)
                    except (TypeError, ValueError):
                        conf = -1
                    if not t or conf < 0:
                        continue
                    words.append(Word(t, x * scale, y * scale, (x + w) * scale, (y + h) * scale, i, round(max(conf, 0) / 100, 3)))
                pt = PageText(i, page.rect.width, page.rect.height, words, group_lines(words, i), self.name if words else "needs_ocr")
                pt.quality = quality
                yield pt