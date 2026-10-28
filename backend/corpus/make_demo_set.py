"""Five synthetic PDFs that exercise different parts of the security scan, each with one real, documented problem."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.identifiers import verhoeff_checksum  # noqa: E402
from corpus.generate import build_scenario, render_scenario  # noqa: E402
from corpus.make_tampered import tamper_net_pay  # noqa: E402


def main() -> None:
    out = Path(__file__).parent / "out" / "demo_set"
    out.mkdir(parents=True, exist_ok=True)
    files = render_scenario(build_scenario(1), out / "src")
    clean = files["salary_slip"]
    shutil.copyfile(clean, out / "payslip_oct_2026.pdf")
    tamper_net_pay(clean, out / "payslip_oct_2026_received.pdf")
    with fitz.open(str(clean)) as d:
        d.set_metadata({**d.metadata, "creationDate": "D:20261028120000+05'30'", "modDate": "D:20240101090000+05'30'"})
        d.save(str(out / "payslip_oct_2026_copy.pdf"))
    with fitz.open(str(clean)) as d:
        d.xref_set_key(d.pdf_catalog(), "OpenAction", "<</S/JavaScript/JS(app.alert('synthetic demo'))>>")
        d.save(str(out / "payslip_oct_2026_email_attachment.pdf"))
    body = "23456789012"
    aadhaar = body + verhoeff_checksum(body)
    c = canvas.Canvas(str(out / "kyc_details_form.pdf"), pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 760
    for line in ["KYC DETAILS FORM", "", "Name: Priya Kumar Verma", f"Aadhaar: {aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}",
                 "PAN: PFZPV6876O", "Mobile: 9876543210", "Email: priya.verma@example.com", "", "Specimen for software testing."]:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    for f in sorted(out.glob("*.pdf")):
        print(f)


if __name__ == "__main__":
    main()