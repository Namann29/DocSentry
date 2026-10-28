import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.extraction.service import run_extraction
from app.identifiers import verhoeff_checksum
from app.security_scan import scan_document
from corpus.generate import build_scenario, render_scenario
from corpus.make_tampered import tamper_net_pay


def _scan(path: Path) -> dict:
    out = run_extraction(path)
    import fitz
    with fitz.open(str(path)) as d:
        meta = {k: v for k, v in (d.metadata or {}).items() if v}
    return scan_document(path, out.pages, [], meta, "x" * 64, path.stat().st_size, "application/pdf")


@pytest.fixture(scope="module")
def slips(tmp_path_factory):
    files = render_scenario(build_scenario(1), tmp_path_factory.mktemp("sec"))
    clean = files["salary_slip"]
    modified = clean.with_name("modified.pdf")
    info = tamper_net_pay(clean, modified)
    return clean, modified, info


def test_clean_generated_slip_has_no_modification_indicators(slips):
    clean, _, _ = slips
    s = _scan(clean)
    assert s["structure"]["incremental_updates"] == 0
    assert s["modification_indicators"] == []
    assert s["score"] < 15 and s["level"] == "Low observed risk"


def test_modified_slip_is_flagged(slips):
    _, modified, info = slips
    s = _scan(modified)
    assert s["structure"]["incremental_updates"] >= 1
    hits = s["modification_indicators"]
    assert hits and any(h["page"] == info["page"] and "75,000" in h["text"] for h in hits)
    assert s["score"] >= 15
    assert any(c["check"] == "mixed_font_numeric" for c in s["contributions"])
    assert "not proof" in next(c for c in s["contributions"] if c["check"] == "mixed_font_numeric")["explanation"]


def test_unmasked_aadhaar_is_reported_masked_only(tmp_path):
    body = "23456789012"
    number = body + verhoeff_checksum(body)
    spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
    pdf = tmp_path / "kyc.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawString(72, 700, f"Aadhaar: {spaced}  Phone: 9876543210  Email: test@example.com")
    c.drawString(72, 680, "Account No: 123456789012")
    c.save()
    s = _scan(pdf)
    kinds = {x["kind"] for x in s["sensitive"]}
    assert {"aadhaar", "mobile", "email", "account"} <= kinds
    dumped = json.dumps(s)
    assert number not in dumped and spaced not in dumped and "9876543210" not in dumped and "123456789012" not in dumped
    assert any(c["check"] == "aadhaar_exposure" for c in s["contributions"])


def test_quick_scan_endpoint(client, users, slips):
    _, modified, _ = slips
    r = client.post("/api/scan", headers=users["analyst"], files=[("file", ("evil.exe", b"MZ\x90\x00", "application/octet-stream"))])
    assert r.status_code == 422
    r = client.post("/api/scan", headers=users["analyst"], files=[("file", ("doc.pdf", modified.read_bytes(), "application/pdf"))])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["doc_type"] == "salary_slip" and body["scan"]["structure"]["incremental_updates"] >= 1
    assert client.get(f"/api/cases/{body['case_id']}", headers=users["analyst2"]).status_code == 403
    r = client.get(f"/api/documents/{body['document_id']}/security", headers=users["analyst"])
    assert r.status_code == 200 and r.json()["score"] == body["scan"]["score"]


def test_forensics_rule_feeds_case_risk(client, users, slips):
    _, modified, _ = slips
    cid = client.post("/api/cases", headers=users["analyst"], json={"title": "Forensics"}).json()["id"]
    client.post(f"/api/cases/{cid}/documents", headers=users["analyst"], files=[("files", ("a.pdf", modified.read_bytes(), "application/pdf"))])
    client.post(f"/api/cases/{cid}/process", headers=users["analyst"])
    findings = client.get(f"/api/cases/{cid}/findings?engine=forensics", headers=users["analyst"]).json()
    assert any(f["severity"] in ("medium", "high") and "different font" in f["title"] for f in findings)