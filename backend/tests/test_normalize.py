from datetime import date
from decimal import Decimal

from app.normalize import (find_amounts, find_dates, format_inr, name_similarity, parse_amount, parse_date,
                           parse_month, surnames_match)


def test_amounts():
    assert parse_amount("1,25,000.00").value == Decimal("125000.00")
    assert parse_amount("Rs. 65,000").value == Decimal("65000.00")
    assert parse_amount("â‚¹45,000.50").value == Decimal("45000.50")
    assert parse_amount("2,500.00 Dr").direction == "DR"
    assert parse_amount("-2,500.00").value == Decimal("-2500.00")
    assert parse_amount("(300.00)").value == Decimal("-300.00")
    assert parse_amount("12/10/2026") is None
    assert parse_amount("") is None
    assert format_inr(Decimal("125000")) == "1,25,000.00"
    assert format_inr(Decimal("999.5")) == "999.50"
    assert format_inr(Decimal("12345678.9")) == "1,23,45,678.90"


def test_find_amounts_ignores_dates_and_ids():
    assert find_amounts("CGST @ 9% 9,533.90") == [Decimal("9533.90")]
    assert find_amounts("Invoice Date: 15/10/2026 PAN ABCPS1234D") == []


def test_dates():
    assert parse_date("15/10/2026") == date(2026, 10, 15)
    assert parse_date("15-Oct-2026") == date(2026, 10, 15)
    assert parse_date("2026-10-15") == date(2026, 10, 15)
    assert parse_date("15/10/26") == date(2026, 10, 15)
    assert parse_date("1,25,000.00") is None
    assert find_dates("Statement Period: 01/08/2026 to 31/10/2026") == [date(2026, 8, 1), date(2026, 10, 31)]
    assert find_dates("since 12 March 2021.") == [date(2021, 3, 12)]
    assert parse_month("OCTOBER 2026") == "2026-10"
    assert parse_month("Oct-2026") == "2026-10"
    assert parse_month("10/2026") == "2026-10"


def test_names():
    assert name_similarity("Rahul Kumar Sharma", "RAHUL K SHARMA") >= 0.9
    assert name_similarity("Mr. Rahul Kumar Sharma", "Sharma Rahul Kumar") >= 0.9
    assert name_similarity("Rahul Kumar Sharma", "Priya Patel") < 0.6
    assert surnames_match("Rahul Kumar Sharma", "R K Sharma")
    assert not surnames_match("Rahul Kumar Sharma", "Rahul Kumar Verma")