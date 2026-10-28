"""Runs the extraction ladder for one file: native text first, OCR when there is no text layer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from ..parsers import ParseResult, get_parser
from .base import ExtractionAdapter, PageText
from .classifier import Classification, classify
from .easyocr_adapter import EasyOCRAdapter, easyocr_available
from .ensemble_adapter import EnsembleOCRAdapter
from .ocr_adapter import TesseractOCRAdapter, ocr_available
from .pymupdf_adapter import PyMuPDFAdapter


KEY_FIELD = {"salary_slip": "net_pay", "bank_statement": "transactions", "invoice": "total", "purchase_order": "po_number",
             "employment_letter": "employee_name", "pan_card": "pan", "aadhaar": "aadhaar_masked"}


@dataclass
class ExtractionOutcome:
    pages: list[PageText]
    classification: Classification
    result: ParseResult | None
    method: str
    text: str


def get_adapter(run_mode: str = settings.run_mode) -> ExtractionAdapter:
    return PyMuPDFAdapter()


def ocr_engine() -> str | None:
    pref = settings.ocr_engine
    if pref == "none":
        return None
    if pref in ("auto", "ensemble") and easyocr_available() and ocr_available():
        return "ensemble"
    if pref in ("auto", "easyocr") and easyocr_available():
        return "easyocr"
    if pref in ("auto", "tesseract") and ocr_available():
        return "tesseract"
    return None


def get_ocr_adapter() -> ExtractionAdapter | None:
    eng = ocr_engine()
    if eng == "ensemble":
        return EnsembleOCRAdapter()
    if eng == "easyocr":
        return EasyOCRAdapter()
    if eng == "tesseract":
        return TesseractOCRAdapter()
    return None


def run_extraction(path: Path, adapter: ExtractionAdapter | None = None, expected_type: str | None = None) -> ExtractionOutcome:
    adapter = adapter or get_adapter()
    pages = list(adapter.extract(path))
    method = adapter.name
    if not any(p.words for p in pages):
        ocr = get_ocr_adapter()
        if ocr is not None:
            pages = list(ocr.extract(path))
            method = ocr.name
        if not any(p.words for p in pages):
            return ExtractionOutcome(pages, Classification("unknown", 0.0, {}), None, "needs_ocr", "")
    text = "\n".join(line.text for p in pages for line in p.lines)
    cls = classify(text, pages)
    cls.scores = dict(cls.scores)
    if expected_type:
        if cls.doc_type == "unknown" and get_parser(expected_type):
            cls = Classification(expected_type, 0.5, {**cls.scores, "_assumed_from_user": 1})
        elif cls.doc_type != expected_type:
            cls.scores["_expected_type_mismatch"] = 1
    parser = get_parser(cls.doc_type)
    result = parser.parse(pages) if parser else None
    key = KEY_FIELD.get(cls.doc_type)
    if result is not None and key and not result.data.get(key):
        cls.scores = {**cls.scores, "_weak_parse": 1}
        cls.confidence = min(cls.confidence, 0.5)
        result.warnings.append(f"Classified as {cls.doc_type} but its key field ({key}) was not found; treat the type as uncertain")
    return ExtractionOutcome(pages, cls, result, method, text)