"""Ensemble OCR: EasyOCR detects and reads every region; Tesseract gives a second opinion on regions where
EasyOCR was unsure; the more plausible read wins. Each page records how many regions each engine won."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import fitz

from ..config import settings
from ..errors import ProcessingError
from .base import ExtractionAdapter, PageText, Word, group_lines
from .easyocr_adapter import reader, split_words
from .ocr_adapter import preprocess, quality_gate, render_page, tesseract_cmd

_OK = re.compile(r"[A-Za-z0-9 /:.,()'-]")
SECOND_OPINION_BELOW = 0.7


def plausibility(text: str) -> float:
    if not text.strip():
        return 0.0
    clean = sum(1 for ch in text if _OK.match(ch)) / len(text)
    tokens = text.split()
    mixed = sum(1 for t in tokens if re.search(r"[A-Za-z]", t) and re.search(r"\d", t)
                and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]|[A-Z]{4}0[A-Z0-9]{6}|\d{2}[A-Z]{5}\d{4}[A-Z]\w{3}", t))
    return max(0.0, clean - 0.25 * mixed / max(len(tokens), 1))


class EnsembleOCRAdapter(ExtractionAdapter):
    name = "ocr_ensemble"

    def extract(self, path: Path) -> Iterator[PageText]:
        import cv2
        import pytesseract
        cmd = tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            doc = fitz.open(str(path))
        except Exception as e:
            raise ProcessingError(f"Cannot open document: {type(e).__name__}") from e
        rd = reader()
        with doc:
            for i, page in enumerate(doc, start=1):
                bgr = render_page(page)
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                quality = quality_gate(gray)
                enhanced, _, angle = preprocess(gray)
                quality["deskew_degrees"] = round(angle, 2)
                results = rd.readtext(bgr, detail=1, paragraph=False, canvas_size=1600, mag_ratio=1.0)
                scale = page.rect.width / bgr.shape[1]
                H, W = gray.shape[:2]
                words: list[Word] = []
                chosen = {"easyocr": 0, "tesseract": 0}
                for box, e_text, e_conf in results:
                    best_text, best_conf, engine = str(e_text), float(e_conf), "easyocr"
                    best_score = best_conf * plausibility(best_text)
                    xs, ys = [p[0] for p in box], [p[1] for p in box]
                    x0, x1 = int(max(0, min(xs) - 6)), int(min(W, max(xs) + 6))
                    y0, y1 = int(max(0, min(ys) - 6)), int(min(H, max(ys) + 6))
                    if cmd and best_conf < SECOND_OPINION_BELOW and x1 - x0 > 12 and y1 - y0 > 8:
                        try:
                            crop = enhanced[y0:y1, x0:x1]
                            if crop.shape[0] < 40:
                                f = 40 / crop.shape[0]
                                crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
                            d = pytesseract.image_to_data(crop, lang=settings.ocr_langs, config="--psm 7", output_type=pytesseract.Output.DICT)
                            toks = [(t.strip(), float(c)) for t, c in zip(d["text"], d["conf"]) if str(t).strip() and float(c) >= 0]
                            if toks:
                                t_text = " ".join(t for t, _ in toks)
                                t_conf = sum(c for _, c in toks) / len(toks) / 100
                                t_score = t_conf * plausibility(t_text)
                                if t_score > best_score:
                                    best_text, best_conf, engine, best_score = t_text, t_conf, "tesseract", t_score
                        except Exception:
                            pass
                    ws = split_words(box, best_text, best_conf, scale, i)
                    if ws:
                        chosen[engine] += 1
                        words.extend(ws)
                pt = PageText(i, page.rect.width, page.rect.height, words, group_lines(words, i), self.name if words else "needs_ocr")
                quality.update({"engine": self.name, "regions_by_engine": chosen,
                                "ocr_mean_confidence": round(sum(w.conf for w in words) / len(words), 3) if words else 0.0})
                pt.quality = quality
                yield pt