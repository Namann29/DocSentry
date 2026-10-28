"""A statement whose header words are unknown to the parser must still parse, by geometry and arithmetic."""
import copy
from decimal import Decimal

from app.extraction.service import run_extraction
from corpus.generate import STATEMENT_TEMPLATES, build_scenario, render_statement


def _render_with_headers(tmp_path, labels, template_base=1, name="odd.pdf"):
    scn = build_scenario(1)
    tmpl = copy.deepcopy(STATEMENT_TEMPLATES[template_base])
    tmpl["cols"] = [(k, labels.get(k, lbl), x, w, al) for k, lbl, x, w, al in tmpl["cols"]]
    STATEMENT_TEMPLATES[990 + template_base] = tmpl
    scn.account.template = 990 + template_base
    path = tmp_path / name
    render_statement(path, scn.account)
    return scn, path


def _recall(scn, txns):
    truth = {(t.date.isoformat(), str(t.balance.quantize(Decimal("0.01")))) for t in scn.account.txns}
    got = {(r["date"], str(Decimal(r["balance"]).quantize(Decimal("0.01")))) for r in txns if r.get("balance")}
    return len(truth & got) / len(truth)


def test_unknown_headers_split_columns(tmp_path):
    scn, path = _render_with_headers(tmp_path, {"date": "Dt", "description": "Memo", "debit": "Out", "credit": "In", "balance": "Bal"})
    out = run_extraction(path)
    assert out.classification.doc_type == "bank_statement"
    txns = out.result.data["transactions"]
    assert _recall(scn, txns) >= 0.9
    assert any("inferred" in w for w in out.result.warnings)
    for got, truth in zip(txns, scn.account.txns):
        assert (Decimal(got["debit"]) if got["debit"] else None) == truth.debit
        assert (Decimal(got["credit"]) if got["credit"] else None) == truth.credit


def test_unknown_headers_single_signed_column(tmp_path):
    scn, path = _render_with_headers(tmp_path, {"serial": "No", "date": "When", "description": "What", "amount": "Movement", "balance": "Left"}, template_base=5, name="signed.pdf")
    out = run_extraction(path)
    txns = out.result.data["transactions"]
    assert _recall(scn, txns) >= 0.9