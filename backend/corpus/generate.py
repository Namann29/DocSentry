"""Synthetic corpus generator: ground truth -> rendered PDFs -> truth.json.
All documents are visibly marked as synthetic and imitate no real credential design.
Templates 1-3 are the development set; 4-5 are HELD OUT (do not tune parsers on them)."""
from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from string import ascii_uppercase

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.identifiers import gstin_checksum  # noqa: E402
from app.normalize import format_inr as inr  # noqa: E402

W, H = A4
BANNER = "Specimen document for software testing - not a real record"
D = Decimal


@dataclass
class Person:
    name: str
    pan: str
    dob: date
    aadhaar_last4: str
    gender: str
    address: str


@dataclass
class Org:
    name: str
    address: str
    gstin: str


@dataclass
class Txn:
    date: date
    description: str
    debit: Decimal | None
    credit: Decimal | None
    balance: Decimal = D(0)


@dataclass
class Account:
    bank: str
    holder: str
    number: str
    ifsc: str
    branch: str
    period_from: date
    period_to: date
    opening: Decimal
    txns: list[Txn]
    template: int
    corrupt_rows: list[int] = field(default_factory=list)  # 1-based row numbers with a wrong balance

    @property
    def closing(self) -> Decimal:
        return self.txns[-1].balance if self.txns else self.opening


@dataclass
class Slip:
    employer: Org
    employee_name: str
    code: str
    designation: str
    month: date
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    account_masked: str
    pan_masked: str
    layout: int

    @property
    def gross(self) -> Decimal:
        return sum(self.earnings.values(), D(0))

    @property
    def total_deductions(self) -> Decimal:
        return sum(self.deductions.values(), D(0))

    @property
    def net(self) -> Decimal:
        return self.gross - self.total_deductions


@dataclass
class Item:
    description: str
    hsn: str
    qty: Decimal
    rate: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.qty * self.rate).quantize(D("0.01"))


@dataclass
class Invoice:
    number: str
    date: date
    supplier: Org
    buyer: Org
    items: list[Item]
    po_ref: str
    place_of_supply: str
    tax_rate: Decimal = D("9")  # CGST and SGST each

    @property
    def taxable(self) -> Decimal:
        return sum((i.amount for i in self.items), D(0))

    @property
    def cgst(self) -> Decimal:
        return (self.taxable * self.tax_rate / 100).quantize(D("0.01"))

    @property
    def total(self) -> Decimal:
        return self.taxable + 2 * self.cgst


@dataclass
class PO:
    number: str
    date: date
    buyer: Org
    vendor: Org
    items: list[Item]

    @property
    def total(self) -> Decimal:
        return (sum((i.amount for i in self.items), D(0)) * D("1.18")).quantize(D("0.01"))


@dataclass
class Letter:
    employer: Org
    employee_name: str
    code: str
    designation: str
    gross_monthly: Decimal
    net_monthly: Decimal
    joining: date
    letter_date: date


@dataclass
class Scenario:
    id: int
    name: str
    person: Person
    employer: Org
    account: Account
    slip: Slip
    letter: Letter
    invoices: list[Invoice]
    po: PO
    aadhaar_name: str
    aadhaar_dob: date


# ------------------------------------------------------------------ truth builders
def mk_pan(rng: random.Random, surname: str) -> str:
    return "".join(rng.choices(ascii_uppercase, k=3)) + "P" + surname[0].upper() + str(rng.randint(1000, 9999)) + rng.choice(ascii_uppercase)


def mk_gstin(rng: random.Random, pan: str) -> str:
    body = rng.choice(["07", "09", "27", "29"]) + pan + "1Z"
    return body + gstin_checksum(body)


DESCS = ["UPI/{0}/SWIGGY ORDER", "UPI/{0}/GROCERY MART", "POS/5412XXXXXXXX3456/CITYMART RETAIL PRIVATE LIMITED/GHAZIABAD",
         "UPI/{0}/METRO CARD RECHARGE", "ATM/CASH WDL/MERIDIAN ATM/VAISHALI", "UPI/{0}/MOBILE RECHARGE",
         "NEFT/OUT/ELECTRICITY BOARD/BILL PAYMENT", "UPI/{0}/PHARMACY"]


def build_txns(rng: random.Random, opening: Decimal, months: list[tuple[int, int]], employer_short: str,
               salary: list[Decimal], supplier_payment: tuple[str, Decimal] | None, rent: Decimal) -> list[Txn]:
    raw: list[Txn] = []
    for mi, (y, m) in enumerate(months):
        raw.append(Txn(date(y, m, 1), f"NEFT-SAL-{employer_short}-{date(y, m, 1):%b%y}".upper(), None, salary[mi]))
        raw.append(Txn(date(y, m, 3), f"UPI/{rng.randint(100000, 999999)}/RENT/HOUSE OWNER", rent, None))
        raw.append(Txn(date(y, m, 7), "ACH/D/ORBIT HOME FINANCE/EMI", D("18500.00"), None))
        for _ in range(rng.randint(4, 6)):
            raw.append(Txn(date(y, m, rng.randint(8, 27)), rng.choice(DESCS).format(rng.randint(100000, 999999)),
                           D(rng.randint(150, 4500)).quantize(D("0.01")), None))
        if mi == len(months) - 1 and supplier_payment:
            raw.append(Txn(date(y, m, 22), f"NEFT/OUT/{supplier_payment[0][:22].upper()}/INV PAYMENT", supplier_payment[1], None))
        if m in (9, 12, 3, 6):
            raw.append(Txn(date(y, m, 30 if m != 12 else 31), "INTEREST CREDIT", None, D(rng.randint(180, 420)).quantize(D("0.01"))))
    raw.sort(key=lambda t: t.date)
    bal = opening
    for t in raw:
        bal = bal - (t.debit or 0) + (t.credit or 0)
        t.balance = bal
    return raw


def build_scenario(sid: int) -> Scenario:
    rng = random.Random(sid * 101)
    first, last = ["Rahul", "Priya", "Amit", "Sneha", "Vikram"][sid % 5], ["Sharma", "Verma", "Patel", "Iyer", "Singh"][sid % 5]
    name = f"{first} Kumar {last}" if sid % 2 else f"{first} {last}"
    pan = mk_pan(rng, last)
    person = Person(name, pan, date(1990, 5, 14), str(rng.randint(1000, 9999)), "Male" if first in ("Rahul", "Amit", "Vikram") else "Female",
                    "H.No 42, Sector 4, Vaishali, Ghaziabad, Uttar Pradesh 201010")
    employer = Org("Meridian Infotech Private Limited", "Plot 7, Sector 62, Noida, Uttar Pradesh 201301", mk_gstin(rng, "AAACD1234E"))
    supplier = Org("Orbit Office Solutions Pvt Ltd", "B-18, Okhla Phase 1, New Delhi 110020", mk_gstin(rng, "AABCD5678F"))
    business = Org(f"{last} Enterprises", person.address, mk_gstin(rng, pan))

    net_target = D("65000.00")
    earnings = {"Basic": D("36000.00"), "HRA": D("14400.00"), "Special Allowance": D("21600.00")}
    deductions = {"Provident Fund": D("4320.00"), "Professional Tax": D("200.00"), "TDS": D("2480.00")}
    salary_credit = D("45000.00") if sid in (2, 5) else net_target
    months = [(2026, 8), (2026, 9), (2026, 10)]
    account_number = str(rng.randint(10**11, 10**12 - 1))

    items1 = [Item("Laptop Workstation 16GB/512GB", "8471", D("2"), D("52966.10"))]
    inv1 = Invoice("INV-2026-0117", date(2026, 10, 15), supplier, business, items1, "PO-2026-0458", "Uttar Pradesh (09)")
    invoices = [inv1]
    payment = inv1.total
    if sid == 3:
        inv2 = Invoice("INV-2026-0117", date(2026, 10, 18), supplier, business,
                       [Item("Laptop Workstation 16GB/512GB", "8471", D("2"), D("61440.68"))], "PO-2026-0458", "Uttar Pradesh (09)")
        invoices.append(inv2)
        payment = inv2.total  # paid the altered duplicate: 1,45,000 vs PO 1,25,000
    po = PO("PO-2026-0458", date(2026, 10, 10), business, supplier, items1)

    txns = build_txns(rng, D("120000.00"), months, "MERIDIANIT", [salary_credit] * 3, (supplier.name, payment), D("22000.00"))
    corrupt: list[int] = []
    if sid == 4:
        corrupt = [14]
        txns[13].balance += D("5000.00")  # row 14 no longer follows from row 13 (row 15 is correct again)
    account = Account("Meridian National Bank", name.upper(), account_number, f"DEMO0{rng.randint(100000, 999999)}", "Vaishali, Ghaziabad",
                      date(2026, 8, 1), date(2026, 10, 31), D("120000.00"), txns, template=((sid - 1) % 5) + 1, corrupt_rows=corrupt)

    slip_name, letter_name, letter_employer, aadhaar_name, aadhaar_dob = name, name, employer, name, person.dob
    slip_account_last4 = account_number[-4:]
    if sid == 5:
        slip_name = f"{first} K. {last}"
        letter_name = f"{first} Kumar Verma" if last != "Verma" else f"{first} Kumar Sharma"
        letter_employer = Org("Meridian Infosys Technologies Ltd", employer.address, employer.gstin)
        aadhaar_dob = date(1990, 5, 24)
        slip_account_last4 = "1234"
    slip = Slip(employer, slip_name, "E1023", "Senior Software Engineer", date(2026, 10, 1), earnings, deductions,
                "XXXXXXXX" + slip_account_last4, pan[:5] + "****" + pan[-1], layout=(sid % 2) + 1)
    letter = Letter(letter_employer, letter_name, "E1023", "Senior Software Engineer", slip.gross, slip.net, date(2021, 3, 12), date(2026, 10, 5))
    names = {1: "consistent", 2: "salary_mismatch", 3: "duplicate_invoice", 4: "broken_balance", 5: "multiple_conflicts"}
    return Scenario(sid, names.get(sid, f"scenario_{sid}"), person, employer, account, slip, letter, invoices, po, aadhaar_name, aadhaar_dob)


# ------------------------------------------------------------------ rendering helpers
def _banner(c: canvas.Canvas, page: int, pages: int) -> None:
    c.setFont("Helvetica", 7)
    c.setFillGray(0.45)
    c.drawString(36, 14, BANNER)
    c.drawRightString(W - 36, 14, f"Page {page} of {pages}")
    c.setFillGray(0)


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    return simpleSplit(text, font, size, width) or [""]


STATEMENT_TEMPLATES = {
    1: dict(font="Helvetica", size=9, fmt="%d/%m/%Y", rows=18, opening_row=True, amount_style="split",
            cols=[("date", "Date", 36, 70, "L"), ("description", "Description", 110, 190, "L"), ("debit", "Debit", 305, 80, "R"),
                  ("credit", "Credit", 390, 80, "R"), ("balance", "Balance", 475, 84, "R")]),
    2: dict(font="Times-Roman", size=9, fmt="%d-%m-%Y", rows=20, opening_row=True, amount_style="split",
            cols=[("serial", "Sr No", 36, 30, "L"), ("date", "Txn Date", 70, 70, "L"), ("description", "Particulars", 145, 170, "L"),
                  ("debit", "Withdrawals", 320, 75, "R"), ("credit", "Deposits", 400, 75, "R"), ("balance", "Closing Balance", 480, 79, "R")]),
    3: dict(font="Helvetica", size=8.5, fmt="%d/%m/%y", rows=22, opening_row=False, amount_style="crdr",
            cols=[("date", "Date", 36, 60, "L"), ("ref", "Ref No", 100, 60, "L"), ("description", "Narration", 165, 200, "L"),
                  ("amount", "Amount (INR)", 370, 95, "R"), ("balance", "Balance", 470, 89, "R")]),
    # ---- HELD OUT: never used while developing the parsers ----
    4: dict(font="Courier", size=8, fmt="%d-%b-%Y", rows=24, opening_row=True, amount_style="split",
            cols=[("date", "Value Date", 36, 75, "L"), ("description", "Narration", 115, 160, "L"), ("ref", "Chq/Ref No", 280, 55, "L"),
                  ("debit", "Withdrawal (Dr)", 340, 70, "R"), ("credit", "Deposit (Cr)", 415, 70, "R"), ("balance", "Running Balance", 490, 69, "R")]),
    5: dict(font="Helvetica", size=9, fmt="%Y-%m-%d", rows=19, opening_row=False, amount_style="signed",
            cols=[("serial", "#", 36, 25, "L"), ("date", "Transaction Date", 66, 70, "L"), ("description", "Transaction Details", 140, 215, "L"),
                  ("amount", "Amount", 360, 95, "R"), ("balance", "Balance (INR)", 460, 99, "R")]),
}


def _bold(font: str) -> str:
    return {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}.get(font, font)


def render_statement(path: Path, a: Account) -> None:
    t = STATEMENT_TEMPLATES[a.template]
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    c.setTitle(f"Synthetic bank statement template {a.template}")
    font, size, fmt = t["font"], t["size"], t["fmt"]
    rows: list[dict] = []
    if t["opening_row"]:
        rows.append({"date": a.period_from, "description": "Opening Balance", "debit": None, "credit": None, "balance": a.opening, "serial": ""})
    for i, x in enumerate(a.txns, 1):
        rows.append({"date": x.date, "description": x.description, "debit": x.debit, "credit": x.credit, "balance": x.balance, "serial": str(i)})
    per = t["rows"]
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)]
    npages = len(chunks)
    desc_x = next(cx for ck, _, cx, _, _ in t["cols"] if ck == "description")
    desc_w = next(cw for ck, _, _, cw, _ in t["cols"] if ck == "description")
    for pi, chunk in enumerate(chunks, 1):
        _banner(c, pi, npages)
        y = H - 50
        c.setFont("Helvetica-Bold", 13)
        c.drawString(36, y, a.bank)
        c.setFont(font, size)
        y -= 16
        c.drawString(36, y, "Account Statement")
        y -= 18
        if pi == 1:
            meta = [f"Account Holder: {a.holder}", f"Account Number: {a.number}", f"IFSC: {a.ifsc}    Branch: {a.branch}",
                    f"Statement Period: {a.period_from.strftime(fmt)} to {a.period_to.strftime(fmt)}    Currency: INR"]
            if not t["opening_row"]:
                meta.append(f"Opening Balance: {inr(a.opening)}")
            for mline in meta:
                c.drawString(36, y, mline)
                y -= 13
            y -= 6
        c.setFont(_bold(font), size)
        for key, label, x, w, al in t["cols"]:
            (c.drawRightString(x + w, y, label) if al == "R" else c.drawString(x, y, label))
        c.line(36, y - 3, W - 36, y - 3)
        c.setFont(font, size)
        y -= 15
        for r in chunk:
            parts = _wrap(r["description"], font, size, desc_w)
            for key, label, x, w, al in t["cols"]:
                if key == "date":
                    c.drawString(x, y, r["date"].strftime(fmt))
                elif key == "serial":
                    c.drawString(x, y, r["serial"])
                elif key == "ref":
                    c.drawString(x, y, "" if r["description"] == "Opening Balance" else f"TXN{abs(hash(r['description'])) % 10**6:06d}")
                elif key == "description":
                    c.drawString(x, y, parts[0])
                elif key == "debit" and r["debit"] is not None:
                    c.drawRightString(x + w, y, inr(r["debit"]))
                elif key == "credit" and r["credit"] is not None:
                    c.drawRightString(x + w, y, inr(r["credit"]))
                elif key == "amount":
                    if r["debit"] is not None:
                        c.drawRightString(x + w, y, inr(-r["debit"]) if t["amount_style"] == "signed" else inr(r["debit"]) + " Dr")
                    elif r["credit"] is not None:
                        c.drawRightString(x + w, y, inr(r["credit"]) if t["amount_style"] == "signed" else inr(r["credit"]) + " Cr")
                elif key == "balance":
                    c.drawRightString(x + w, y, inr(r["balance"]))
            for extra in parts[1:]:
                y -= 11
                c.drawString(desc_x, y, extra)
            y -= 13
        if pi == npages:
            y -= 8
            c.drawString(36, y, f"Closing Balance: {inr(a.closing)}")
            y -= 13
            c.drawString(36, y, "Specimen statement for software testing. It does not represent a real account.")
        c.showPage()
    c.save()


def render_slip(path: Path, s: Slip) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 50
    c.setFont("Helvetica-Bold", 13)
    c.drawString(36, y, s.employer.name)
    c.setFont("Helvetica", 9)
    y -= 14
    c.drawString(36, y, s.employer.address)
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    title = f"SALARY SLIP FOR THE MONTH OF {s.month:%B %Y}".upper() if s.layout == 1 else f"Payslip - Pay Period: {s.month:%b-%Y}"
    c.drawString(36, y, title)
    c.setFont("Helvetica", 9)
    y -= 20
    meta = [(f"Employee Name: {s.employee_name}", f"Employee Code: {s.code}"), (f"Designation: {s.designation}", "Department: Engineering"),
            (f"PAN: {s.pan_masked}", f"Bank A/c No: {s.account_masked}"), ("UAN: 100123456789", "Paid Days: 31")]
    for left, right in meta:
        c.drawString(36, y, left)
        c.drawString(320, y, right)
        y -= 13
    y -= 10
    if s.layout == 1:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y, "EARNINGS")
        c.drawRightString(280, y, "Amount (Rs.)")
        c.drawString(320, y, "DEDUCTIONS")
        c.drawRightString(559, y, "Amount (Rs.)")
        c.line(36, y - 3, W - 36, y - 3)
        c.setFont("Helvetica", 9)
        y -= 16
        e, d = list(s.earnings.items()), list(s.deductions.items())
        for i in range(max(len(e), len(d))):
            if i < len(e):
                c.drawString(36, y, e[i][0])
                c.drawRightString(280, y, inr(e[i][1]))
            if i < len(d):
                c.drawString(320, y, d[i][0])
                c.drawRightString(559, y, inr(d[i][1]))
            y -= 13
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y, "Gross Earnings")
        c.drawRightString(280, y, inr(s.gross))
        c.drawString(320, y, "Total Deductions")
        c.drawRightString(559, y, inr(s.total_deductions))
        y -= 20
        c.drawString(36, y, f"Net Pay: Rs. {inr(s.net)}")
    else:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y, "Earnings")
        y -= 13
        c.setFont("Helvetica", 9)
        labels = {"Basic": "Basic Pay", "HRA": "House Rent Allowance", "Special Allowance": "Special Allowance",
                  "Provident Fund": "EPF Employee Contribution", "Professional Tax": "Prof. Tax", "TDS": "Income Tax (TDS)"}
        for k, v in s.earnings.items():
            c.drawString(50, y, labels.get(k, k))
            c.drawRightString(300, y, f"{v:.2f}")
            y -= 12
        c.drawString(50, y, "Total Earnings")
        c.drawRightString(300, y, f"{s.gross:.2f}")
        y -= 16
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y, "Deductions")
        y -= 13
        c.setFont("Helvetica", 9)
        for k, v in s.deductions.items():
            c.drawString(50, y, labels.get(k, k))
            c.drawRightString(300, y, f"{v:.2f}")
            y -= 12
        c.drawString(50, y, "Total Deductions")
        c.drawRightString(300, y, f"{s.total_deductions:.2f}")
        y -= 18
        c.setFont("Helvetica-Bold", 10)
        c.drawString(36, y, "Net Salary Payable")
        c.drawRightString(300, y, f"{s.net:.2f}")
    y -= 20
    c.setFont("Helvetica", 8)
    c.drawString(36, y, "This is a computer generated payslip and does not require a signature. Specimen for software testing.")
    c.showPage()
    c.save()


def _items_table(c: canvas.Canvas, y: float, items: list[Item]) -> float:
    c.setFont("Helvetica-Bold", 9)
    heads = [("Sr No", 36, 35, "L"), ("Description", 76, 220, "L"), ("HSN/SAC", 300, 60, "L"), ("Qty", 365, 35, "R"), ("Rate", 405, 70, "R"), ("Amount", 480, 79, "R")]
    for label, x, w, al in heads:
        (c.drawRightString(x + w, y, label) if al == "R" else c.drawString(x, y, label))
    c.line(36, y - 3, W - 36, y - 3)
    c.setFont("Helvetica", 9)
    y -= 15
    for i, it in enumerate(items, 1):
        c.drawString(36, y, str(i))
        c.drawString(76, y, it.description)
        c.drawString(300, y, it.hsn)
        c.drawRightString(400, y, f"{it.qty:.0f}")
        c.drawRightString(475, y, inr(it.rate))
        c.drawRightString(559, y, inr(it.amount))
        y -= 13
    c.line(36, y + 6, W - 36, y + 6)
    return y


def render_invoice(path: Path, inv: Invoice) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(36, y, "TAX INVOICE")
    y -= 22
    c.setFont("Helvetica-Bold", 12)
    c.drawString(36, y, inv.supplier.name)
    c.setFont("Helvetica", 9)
    y -= 13
    c.drawString(36, y, inv.supplier.address)
    y -= 13
    c.drawString(36, y, f"GSTIN: {inv.supplier.gstin}")
    y -= 20
    c.drawString(36, y, f"Invoice No: {inv.number}")
    c.drawString(320, y, f"Invoice Date: {inv.date:%d/%m/%Y}")
    y -= 13
    c.drawString(36, y, f"PO Ref: {inv.po_ref}")
    c.drawString(320, y, f"Place of Supply: {inv.place_of_supply}")
    y -= 20
    c.drawString(36, y, f"Bill To: {inv.buyer.name}")
    y -= 13
    c.drawString(36, y, inv.buyer.address)
    y -= 13
    c.drawString(36, y, f"GSTIN: {inv.buyer.gstin}")
    y -= 24
    y = _items_table(c, y, inv.items)
    y -= 6
    for label, val in [("Taxable Value", inv.taxable), (f"CGST @ {inv.tax_rate}%", inv.cgst), (f"SGST @ {inv.tax_rate}%", inv.cgst), ("Total", inv.total)]:
        c.drawString(380, y, label)
        c.drawRightString(559, y, inr(val))
        y -= 13
    y -= 10
    c.setFont("Helvetica", 8)
    c.drawString(36, y, "Amount in words: as per total above. Synthetic invoice for software testing only.")
    y -= 24
    c.drawString(380, y, f"For {inv.supplier.name}")
    y -= 24
    c.drawString(380, y, "Authorised Signatory")
    c.showPage()
    c.save()


def render_po(path: Path, po: PO) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(36, y, "PURCHASE ORDER")
    y -= 22
    c.setFont("Helvetica-Bold", 12)
    c.drawString(36, y, po.buyer.name)
    c.setFont("Helvetica", 9)
    y -= 13
    c.drawString(36, y, po.buyer.address)
    y -= 13
    c.drawString(36, y, f"GSTIN: {po.buyer.gstin}")
    y -= 20
    c.drawString(36, y, f"PO No: {po.number}")
    c.drawString(320, y, f"PO Date: {po.date:%d/%m/%Y}")
    y -= 13
    c.drawString(36, y, f"Vendor: {po.vendor.name}")
    c.drawString(320, y, f"Delivery Date: {(po.date + timedelta(days=10)):%d/%m/%Y}")
    y -= 13
    c.drawString(36, y, f"Vendor GSTIN: {po.vendor.gstin}")
    y -= 24
    y = _items_table(c, y, po.items)
    y -= 6
    c.drawString(380, y, "Order Total (incl. GST 18%)")
    c.drawRightString(559, y, inr(po.total))
    y -= 24
    c.setFont("Helvetica", 8)
    c.drawString(36, y, "Please mention the PO number on the invoice. Synthetic purchase order for software testing only.")
    c.showPage()
    c.save()


def render_letter(path: Path, lt: Letter) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 50
    c.setFont("Helvetica-Bold", 13)
    c.drawString(36, y, lt.employer.name)
    c.setFont("Helvetica", 9)
    y -= 14
    c.drawString(36, y, lt.employer.address)
    y -= 24
    c.drawString(36, y, f"Date: {lt.letter_date:%d %B %Y}")
    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(36, y, "TO WHOMSOEVER IT MAY CONCERN")
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(36, y, "Employment Verification Letter")
    y -= 20
    c.setFont("Helvetica", 10)
    body = (f"This is to certify that Mr. {lt.employee_name} (Employee Code {lt.code}) is employed with {lt.employer.name} "
            f"as a {lt.designation} since {lt.joining:%d %B %Y}. His current gross monthly salary is Rs. {inr(lt.gross_monthly)} and "
            f"net monthly salary is Rs. {inr(lt.net_monthly)}. This letter is issued at the request of the employee for the purpose of a loan application.")
    for ln in _wrap(body, "Helvetica", 10, W - 72):
        c.drawString(36, y, ln)
        y -= 14
    y -= 20
    c.drawString(36, y, "Sincerely,")
    y -= 28
    c.drawString(36, y, "Authorised Signatory")
    y -= 14
    c.drawString(36, y, "Human Resources")
    c.showPage()
    c.save()


def render_pan(path: Path, p: Person) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 60
    c.setFont("Helvetica-Bold", 13)
    c.drawString(36, y, "PAN DETAILS (SPECIMEN)")
    c.setFont("Helvetica", 10)
    y -= 24
    for line in [f"Permanent Account Number: {p.pan}", f"Name: {p.name.upper()}", f"Father's Name: SURESH {p.name.split()[-1].upper()}",
                 f"Date of Birth: {p.dob:%d/%m/%Y}", "This specimen imitates no official PAN card design."]:
        c.drawString(36, y, line)
        y -= 16
    c.showPage()
    c.save()


def render_aadhaar(path: Path, p: Person, name: str, dob: date) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setAuthor("DocSentry corpus generator")
    _banner(c, 1, 1)
    y = H - 60
    c.setFont("Helvetica-Bold", 13)
    c.drawString(36, y, "AADHAAR OFFLINE e-KYC SUMMARY (SPECIMEN)")
    c.setFont("Helvetica", 10)
    y -= 24
    for line in [f"Aadhaar Number (masked): XXXX XXXX {p.aadhaar_last4}", f"Name: {name}", f"Date of Birth: {dob:%d-%m-%Y}",
                 f"Gender: {p.gender}", f"Address: {p.address}", "Resident data shown as masked. This specimen imitates no official design."]:
        c.drawString(36, y, line)
        y -= 16
    c.showPage()
    c.save()


# ------------------------------------------------------------------ orchestration
def _json(o):  # noqa: ANN001
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def render_scenario(scn: Scenario, out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "bank_statement": out / "bank_statement.pdf", "salary_slip": out / "salary_slip.pdf", "pan_card": out / "pan_details.pdf",
        "aadhaar": out / "aadhaar_ekyc_summary.pdf", "employment_letter": out / "employment_letter.pdf",
        "invoice": out / "invoice.pdf", "purchase_order": out / "purchase_order.pdf",
    }
    render_statement(files["bank_statement"], scn.account)
    render_slip(files["salary_slip"], scn.slip)
    render_pan(files["pan_card"], scn.person)
    render_aadhaar(files["aadhaar"], scn.person, scn.aadhaar_name, scn.aadhaar_dob)
    render_letter(files["employment_letter"], scn.letter)
    render_invoice(files["invoice"], scn.invoices[0])
    render_po(files["purchase_order"], scn.po)
    if len(scn.invoices) > 1:
        files["invoice_2"] = out / "invoice_2.pdf"
        render_invoice(files["invoice_2"], scn.invoices[1])
    truth = asdict(scn)
    truth["slip"].update({"gross": scn.slip.gross, "net": scn.slip.net, "total_deductions": scn.slip.total_deductions})
    truth["invoices"] = [dict(asdict(i), taxable=i.taxable, cgst=i.cgst, total=i.total) for i in scn.invoices]
    truth["po"]["total"] = scn.po.total
    (out / "truth.json").write_text(json.dumps(truth, default=_json, indent=2), encoding="utf-8")
    return files


def main(out_root: Path | None = None) -> None:
    out_root = out_root or Path(__file__).parent / "out"
    for sid in range(1, 6):
        scn = build_scenario(sid)
        files = render_scenario(scn, out_root / f"scenario_{sid}_{scn.name}")
        print(f"scenario {sid} ({scn.name}, statement template {scn.account.template}): {len(files)} files")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)