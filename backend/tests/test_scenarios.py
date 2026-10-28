"""The five demo scenarios: expected results live ONLY here. Documents are uploaded through the
HTTP API with generic names, so nothing is keyed on a filename or a scenario id."""
from decimal import Decimal

import pytest

from corpus.generate import build_scenario, render_scenario


def _run_scenario(client, hdr, sid, tmp_path):
    scn = build_scenario(sid)
    files = render_scenario(scn, tmp_path / str(sid))
    cid = client.post("/api/cases", headers=hdr, json={"title": f"Case {sid}", "case_type": "loan"}).json()["id"]
    uploads = [("files", (f"document_{i}.pdf", p.read_bytes(), "application/pdf")) for i, p in enumerate(files.values(), 1)]
    r = client.post(f"/api/cases/{cid}/documents", headers=hdr, files=uploads)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/cases/{cid}/process", headers=hdr)
    assert r.status_code == 200, r.text
    findings = client.get(f"/api/cases/{cid}/findings", headers=hdr).json()
    risk = client.get(f"/api/cases/{cid}/risk", headers=hdr).json()
    return scn, cid, r.json(), findings, risk


def _by_rule(findings, rule_id, min_sev=("low", "medium", "high")):
    return [f for f in findings if f["rule_id"] == rule_id and f["severity"] in min_sev]


@pytest.fixture(scope="module")
def hdr(users):
    return users["analyst"]


def test_scenario_1_consistent(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 1, tmp_path)
    assert summary["processed"] == 7 and summary["failed"] == []
    assert not [f for f in findings if f["severity"] in ("medium", "high")], [f["title"] for f in findings if f["severity"] in ("medium", "high")]
    assert risk["outcome"] == "Low observed risk"
    assert risk["evidence_coverage"] >= 0.9
    assert any(f["rule_id"] == "cross_document.salary_vs_bank" and f["severity"] == "info" for f in findings)


def test_scenario_2_salary_mismatch(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 2, tmp_path)
    hits = _by_rule(findings, "cross_document.salary_vs_bank")
    assert hits, [f["title"] for f in findings]
    f = hits[0]
    assert "65,000.00" in f["title"] and "45,000.00" in f["title"] and "20,000.00" in f["title"]
    assert {e["doc_type"] for e in f["evidence"]} == {"salary_slip", "bank_statement"}
    assert risk["outcome"] in ("Review recommended", "High observed risk")


def test_scenario_3_duplicate_invoice(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 3, tmp_path)
    dup = _by_rule(findings, "cross_document.duplicate_invoice_numbers", ("high",))
    assert dup and "1,25,000.00" in dup[0]["title"] and "1,45,000.00" in dup[0]["title"]
    over = _by_rule(findings, "cross_document.po_vs_payment")
    assert over and "20,000.00" in over[0]["title"]
    assert _by_rule(findings, "cross_document.invoice_vs_po")
    assert risk["outcome"] == "High observed risk"


def test_scenario_4_broken_running_balance(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 4, tmp_path)
    rb = _by_rule(findings, "financial.running_balance")
    assert rb, [f["title"] for f in findings]
    rows = {e.get("row") for f in rb for e in f["evidence"] if e.get("row")}
    assert 14 in rows
    assert any(e.get("repair_candidates") for f in rb for e in f["evidence"])
    assert risk["outcome"] in ("Review recommended", "High observed risk")


def test_scenario_5_multiple_conflicts(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 5, tmp_path)
    assert _by_rule(findings, "identity.name_consistency", ("high",))
    assert _by_rule(findings, "identity.dob_consistency", ("high",))
    assert _by_rule(findings, "identity.employer_consistency")
    assert _by_rule(findings, "identity.account_consistency")
    assert _by_rule(findings, "cross_document.salary_vs_bank")
    assert risk["outcome"] == "High observed risk"


def test_ablation_single_document_rules_only(client, hdr, tmp_path):
    scn = build_scenario(2)
    files = render_scenario(scn, tmp_path / "abl")
    cid = client.post("/api/cases", headers=hdr, json={"title": "Ablation"}).json()["id"]
    client.post(f"/api/cases/{cid}/documents", headers=hdr,
                files=[("files", (f"d{i}.pdf", p.read_bytes(), "application/pdf")) for i, p in enumerate(files.values())])
    r = client.post(f"/api/cases/{cid}/process", headers=hdr, params={"engines": "identity,financial"})
    assert r.status_code == 200
    findings = client.get(f"/api/cases/{cid}/findings", headers=hdr).json()
    assert not [f for f in findings if f["engine"] == "cross_document"]
    assert not _by_rule(findings, "cross_document.salary_vs_bank")  # the mismatch is invisible without cross-document rules


def test_report_download_and_review(client, users, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 2, tmp_path / "rep")
    r = client.get(f"/api/cases/{cid}/report.pdf", headers=hdr)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 5000
    assert client.post(f"/api/cases/{cid}/review", headers=hdr, json={"outcome": "escalate"}).status_code == 403
    assert client.post(f"/api/cases/{cid}/review", headers=users["reviewer"], json={"outcome": "escalate", "note": "salary gap"}).status_code == 200
    assert client.get(f"/api/cases/{cid}", headers=hdr).json()["review_outcome"] == "escalate"


def test_field_correction_feeds_reprocessing(client, hdr, tmp_path):
    scn, cid, summary, findings, risk = _run_scenario(client, hdr, 2, tmp_path / "corr")
    docs = client.get(f"/api/cases/{cid}/documents", headers=hdr).json()
    slip = next(d for d in docs if d["doc_type"] == "salary_slip")
    fields = client.get(f"/api/documents/{slip['id']}/fields", headers=hdr).json()
    net = next(f for f in fields if f["name"] == "net_pay")
    r = client.patch(f"/api/documents/{slip['id']}/fields/{net['id']}", headers=hdr, json={"value": "45000.00"})
    assert r.status_code == 200 and r.json()["corrected"] is True and r.json()["original_value"] == net["value"]
    client.post(f"/api/cases/{cid}/process", headers=hdr, params={"force": "true"})
    findings = client.get(f"/api/cases/{cid}/findings", headers=hdr).json()
    assert not _by_rule(findings, "cross_document.salary_vs_bank")  # corrected value removes the discrepancy
    stats = client.get(f"/api/cases/{cid}/extraction-stats", headers=hdr).json()
    assert stats["corrected"] == 1 and stats["correction_rate"] > 0


def test_demo_endpoint_uses_same_pipeline(client, hdr):
    r = client.post("/api/demo/scenarios/3", headers=hdr)
    assert r.status_code == 201
    case = r.json()
    assert case["risk_outcome"] == "High observed risk" and case["document_count"] == 8