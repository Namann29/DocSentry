"""Rasterise synthetic documents to PNG (optionally slightly rotated) so the OCR rung can be demonstrated honestly."""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from corpus.generate import build_scenario, render_scenario  # noqa: E402


def rasterise(pdf: Path, png: Path, dpi: int = 200, rotate: float = 0.0) -> Path:
    with fitz.open(str(pdf)) as doc:
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72).prerotate(rotate), alpha=False)
        pix.save(str(png))
    return png


def main() -> None:
    out = Path(__file__).parent / "out" / "images"
    out.mkdir(parents=True, exist_ok=True)
    files = render_scenario(build_scenario(1), out / "src")
    made = [rasterise(files["pan_card"], out / "pan_details_scan.png"),
            rasterise(files["aadhaar"], out / "aadhaar_summary_scan.png", rotate=1.5),
            rasterise(files["salary_slip"], out / "salary_slip_photo.png", dpi=150, rotate=-2.0)]
    for m in made:
        print(m)


if __name__ == "__main__":
    main()