"""Real generated PDFs go through the real extraction ladder. Expected values come from the
generator's ground truth, never from filenames."""
from decimal import Decimal

import pytest

from app.extraction.service import run_extraction
from corpus.generate import build_scenario, render_scenario


@pytest.fixture(scope="module", params=[1, 2, 3])
def scenario(request, tmp_path_factory):
    scn = build_scenario(request.param)
    files = render_scenario(scn, tmp_path_factory.mktemp(f"s{request.param}"))
    return scn, files


def test_every_document_is_classified_correctly(scenario):
    scn, files = scenario
    for key, path in files.items():
        out = run_extraction(path)
        expected = "invoice" if key == "invoice_2" else key
        assert out.classification.doc_type == expected, (key, out.classification)


def test_statement_transactions_match_truth(scenario):
    scn, files = scenario
    out = run_extraction(files["bank_statement"])
    txns = out.result.data["transactions"]
    assert len(txns) == len(scn.account.txns)
    for got, truth in zip(txns, scn.account.txns):
        assert got["date"] == truth.date.isoformat()
        assert Decimal(got["balance"]) == truth.balance
        assert (Decimal(got["debit"]) if got["debit"] else None) == truth.debit
        assert (Decimal(got["credit"]) if got["credit"] else None) == truth.credit
    assert Decimal(out.result.data["opening_balance"]) == scn.account.opening
    assert Decimal(out.result.data["closing_balance"]) == scn.account.closing
    assert out.result.data["ifsc"] == scn.account.ifsc


def test_salary_slip_totals(scenario):
    scn, files = scenario
    out = run_extraction(files["salary_slip"])
    d = out.result.data
    assert Decimal(d["net_pay"]) == scn.slip.net
    assert Decimal(d["earnings_total"]) == scn.slip.gross
    assert Decimal(d["deductions_total"]) == scn.slip.total_deductions
    assert d["month"] == "2026-10"
    assert d["employee_code"] == "E1023"


def test_invoice_and_po(scenario):
    scn, files = scenario
    inv = run_extraction(files["invoice"]).result.data
    assert inv["invoice_number"] == scn.invoices[0].number
    assert Decimal(inv["total"]) == scn.invoices[0].total
    assert Decimal(inv["items_total"]) == scn.invoices[0].taxable
    assert inv["supplier_gstin"] == scn.invoices[0].supplier.gstin
    assert inv["buyer_gstin"] == scn.invoices[0].buyer.gstin
    po = run_extraction(files["purchase_order"]).result.data
    assert po["po_number"] == scn.po.number
    assert Decimal(po["total"]) == scn.po.total


def test_identity_documents(scenario):
    scn, files = scenario
    pan = run_extraction(files["pan_card"]).result.data
    assert pan["pan"] == scn.person.pan and pan["dob"] == scn.person.dob.isoformat()
    aad = run_extraction(files["aadhaar"]).result.data
    assert aad["aadhaar_masked"].endswith(scn.person.aadhaar_last4)
    assert "aadhaar_token" not in aad  # masked input: nothing to hash, nothing stored
    letter = run_extraction(files["employment_letter"]).result.data
    assert letter["employee_name"] == scn.letter.employee_name
    assert Decimal(letter["net_monthly_salary"]) == scn.letter.net_monthly
    assert letter["joining_date"] == scn.letter.joining.isoformat()