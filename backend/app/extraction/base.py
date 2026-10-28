"""Extraction adapter interface and page/line/word geometry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    conf: float = 1.0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    page: int
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def y(self) -> float:
        return median([w.cy for w in self.words])

    @property
    def bbox(self) -> list[float]:
        return bbox_of(self.words)

    @property
    def conf(self) -> float:
        return min(w.conf for w in self.words) if self.words else 0.0


@dataclass
class PageText:
    number: int
    width: float
    height: float
    words: list[Word]
    lines: list[Line]
    method: str  # native_pdf | ocr_tesseract | textract | needs_ocr
    quality: dict | None = None  # OCR quality gate, when applicable


def bbox_of(words: list[Word]) -> list[float]:
    if not words:
        return [0.0, 0.0, 0.0, 0.0]
    return [min(w.x0 for w in words), min(w.y0 for w in words),
            max(w.x1 for w in words), max(w.y1 for w in words)]


def group_lines(words: list[Word], page: int) -> list[Line]:
    """Cluster words into lines by vertical centre, then order each line left-to-right."""
    if not words:
        return []
    tol = max(2.0, 0.45 * median([w.y1 - w.y0 for w in words]))
    ws = sorted(words, key=lambda w: (w.cy, w.x0))
    lines: list[Line] = []
    cur, cur_y = [ws[0]], ws[0].cy
    for w in ws[1:]:
        if abs(w.cy - cur_y) <= tol:
            cur.append(w)
            cur_y = (cur_y * (len(cur) - 1) + w.cy) / len(cur)
        else:
            lines.append(Line(page, sorted(cur, key=lambda x: x.x0)))
            cur, cur_y = [w], w.cy
    lines.append(Line(page, sorted(cur, key=lambda x: x.x0)))
    return lines


class ExtractionAdapter(ABC):
    """Rung of the extraction ladder. Subclasses: PyMuPDF (native), OCR, Textract."""
    name: str = "abstract"

    @abstractmethod
    def extract(self, path: Path) -> Iterator[PageText]:
        """Yield pages lazily so large documents never sit fully in memory."""