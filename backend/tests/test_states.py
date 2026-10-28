"""States must be distinguishable: unknown document, weakly classified document, clean document, not-yet-analysed case."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _pdf(path, lines):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 760
    for ln in lines:
        c.drawString(72, y, ln)
        y -= 18
    c.save()
    return path.read_bytes()


def test_unrelated_pdf_is_unknown_with_no_fields_and_no_zero_totals(client, users, tmp_path):
    data = _pdf(tmp_path / "notes.pdf", ["Meeting notes", "Agenda: project timeline and venue booking", "Attendees: four people", "Next meeting in two weeks"])
    r = client.post("/api/scan", headers=users["analyst"], files=[("file", ("notes.pdf", data, "application/pdf"))])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["doc_type"] == "unknown" and body["status"] == "unsupported"
    assert body["fields"] == {}
    assert body["scan"] is not None and body["scan"]["structure"]["has_text_layer"] is True


def test_report_pdf_is_not_presented_as_a_confident_salary_slip(client, users):
    case = client.post("/api/demo/scenarios/1", headers=users["analyst"]).json()
    pdf = client.get(f"/api/cases/{case['id']}/report.pdf", headers=users["analyst"]).content
    r = client.post("/api/scan", headers=users["analyst"], files=[("file", ("report.pdf", pdf, "application/pdf"))])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["doc_type"] == "unknown" or body["weak_parse"] is True
    assert "earnings_total" not in body["fields"] and "deductions_total" not in body["fields"]


def test_new_case_has_no_score_until_processed(client, users):
    cid = client.post("/api/cases", headers=users["analyst"], json={"title": "Untouched"}).json()["id"]
    risk = client.get(f"/api/cases/{cid}/risk", headers=users["analyst"]).json()
    assert risk["breakdown"] == {} and risk["outcome"] == "Insufficient evidence" and risk["score"] == 0

def test_weakly_classified_document_produces_no_type_specific_findings(client, users):
    case = client.post("/api/demo/scenarios/1", headers=users["analyst"]).json()
    pdf = client.get(f"/api/cases/{case['id']}/report.pdf", headers=users["analyst"]).content
    r = client.post("/api/scan", headers=users["analyst"], files=[("file", ("report.pdf", pdf, "application/pdf"))])
    body = r.json()
    findings = client.get(f"/api/cases/{body['case_id']}/findings", headers=users["analyst"]).json()
    assert not [f for f in findings if f["engine"] in ("financial", "identity", "cross_document")], [f["title"] for f in findings]
    risk = client.get(f"/api/cases/{body['case_id']}/risk", headers=users["analyst"]).json()
    assert risk["outcome"] == "Insufficient evidence" and risk["breakdown"]["insufficient_reason"]
