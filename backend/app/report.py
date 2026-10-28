"""Investigation report PDF (ReportLab platypus)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .engines.base import LEVEL_NAMES
from .models import AuditEvent, Case, Document, Finding
from .normalize import format_inr

NAVY = colors.HexColor("#0f2342")
SLATE = colors.HexColor("#475569")


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _table(rows: list[list[str]], widths: list[float], body: ParagraphStyle, head: ParagraphStyle) -> Table:
    data = [[_p(c, head) for c in rows[0]]] + [[_p(c, body) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
    return t


def _amt(v) -> str:  # noqa: ANN001
    try:
        return format_inr(Decimal(str(v))) if v not in (None, "") else "-"
    except Exception:
        return str(v)


def build_report(case: Case, documents: list[Document], findings: list[Finding], events: list[AuditEvent]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"DocSentry report - case {case.id}", author="DocSentry")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=NAVY, fontSize=18, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=NAVY, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5, textColor=SLATE)
    head = ParagraphStyle("h", parent=body, textColor=colors.white, fontName="Helvetica-Bold")
    W = A4[0] - 36 * mm
    story = [_p("DocSentry Investigation Report", h1),
             _p(f"Case #{case.id}: {case.title}", h2),
             _p(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Outcome: {case.risk_outcome}. Score {case.risk_score}/100. "
                f"Evidence coverage {case.evidence_coverage:.0%}. Extraction quality {case.extraction_quality:.2f}. "
                f"Risk policy v{(case.risk_breakdown or {}).get('policy_version', '-')}.", body),
             _p("This report contains investigation recommendations, not fraud judgements. Format checks never establish authenticity. "
                "External authoritative verification was NOT PERFORMED.", small)]

    story.append(_p("1. Documents", h2))
    rows = [["File", "Type", "Pages", "Status", "SHA-256", "Flags"]]
    for d in documents:
        rows.append([d.original_filename, d.doc_type, str(d.page_count), d.status, d.sha256[:16] + "...", ", ".join(d.security_flags or []) or "-"])
    story.append(_table(rows, [W * 0.26, W * 0.15, W * 0.07, W * 0.11, W * 0.21, W * 0.2], body, head))

    story.append(_p("2. Extraction summary", h2))
    total_fields = sum(len(d.fields) for d in documents)
    corrected = sum(1 for d in documents for f in d.fields if f.corrected)
    story.append(_p(f"{total_fields} fields extracted across {len(documents)} documents; {corrected} manually corrected "
                    f"(correction rate {corrected / total_fields:.1%} if measured over extracted fields)." if total_fields else "No fields extracted.", body))
    for d in documents:
        if d.status != "processed":
            story.append(_p(f"{d.original_filename}: {d.status} - {d.error_message}", small))

    story.append(_p("3. Verification results by taxonomy level", h2))
    for lvl in range(1, 7):
        fl = [f for f in findings if f.level == lvl]
        story.append(_p(f"Level {lvl}: {LEVEL_NAMES[lvl]} ({len(fl)})" + (" - NOT_PERFORMED: no authorised integration exists" if lvl == 5 else ""), ParagraphStyle("l", parent=body, fontName="Helvetica-Bold")))
        for f in fl:
            story.append(_p(f"[{f.severity}] {f.title}" + (" (possible extraction error)" if f.possible_extraction_error else ""), body))

    story.append(_p("4. Financial analysis", h2))
    for d in documents:
        p = d.parsed or {}
        if d.doc_type == "bank_statement":
            story.append(_p(f"Bank statement {d.original_filename}: {p.get('transaction_count', 0)} transactions, period {p.get('period_from', '?')} to {p.get('period_to', '?')}, "
                            f"opening {_amt(p.get('opening_balance'))}, closing {_amt(p.get('closing_balance'))}.", body))
        elif d.doc_type == "salary_slip":
            story.append(_p(f"Salary slip {d.original_filename}: month {p.get('month', '?')}, gross {_amt(p.get('gross'))}, deductions {_amt(p.get('total_deductions'))}, net {_amt(p.get('net_pay'))}.", body))
        elif d.doc_type == "invoice":
            story.append(_p(f"Invoice {p.get('invoice_number', '?')} ({d.original_filename}): taxable {_amt(p.get('taxable_value'))}, total {_amt(p.get('total'))}, PO ref {p.get('po_ref', '-')}.", body))
        elif d.doc_type == "purchase_order":
            story.append(_p(f"Purchase order {p.get('po_number', '?')}: total {_amt(p.get('total'))}, vendor {p.get('vendor', '-')}.", body))

    story.append(_p("5. Cross-document discrepancies", h2))
    cross = [f for f in findings if f.engine == "cross_document" and f.severity != "info"]
    if not cross:
        story.append(_p("No cross-document discrepancies above informational level.", body))
    for f in cross:
        story.append(_p(f"[{f.severity}] {f.title}", ParagraphStyle("c", parent=body, fontName="Helvetica-Bold")))
        story.append(_p(f.explanation, small))

    story.append(_p("6. Risk breakdown", h2))
    rows = [["Rule", "Severity", "Level", "Points", "Finding"]]
    for c in (case.risk_breakdown or {}).get("contributions", []):
        if c["points"] or c["severity"] != "info":
            rows.append([c["rule_id"], c["severity"], str(c["level"]), str(c["points"]) + (" (halved)" if c["extraction_discounted"] else ""), c["title"]])
    if len(rows) == 1:
        rows.append(["-", "-", "-", "0", "No scoring findings"])
    story.append(_table(rows, [W * 0.24, W * 0.1, W * 0.07, W * 0.1, W * 0.49], body, head))
    bd = case.risk_breakdown or {}
    story.append(_p(f"Points table {bd.get('points_table')}; thresholds {bd.get('thresholds')}; raw points {bd.get('raw_points')}, capped {bd.get('capped_score')}.", small))

    story.append(_p("6b. Document security scan", h2))
    for d in documents:
        s = (d.parsed or {}).get("_security")
        if not s:
            story.append(_p(f"{d.original_filename}: not scanned", small))
            continue
        st = s.get("structure", {})
        story.append(_p(f"{d.original_filename}: security score {s.get('score')}/100 ({s.get('level')}); incremental updates {st.get('incremental_updates', '-')}; "
                        f"modification indicators {len(s.get('modification_indicators', []))}; sensitive identifiers {len(s.get('sensitive', []))}; "
                        f"producer {s.get('metadata', {}).get('producer') or '-'}.", body))
        for n in s.get("not_checked", []):
            story.append(_p(f"  not checked: {n['check']} ({n['reason']})", small))
    story.append(_p("Scores summarise observed indicators; they are not determinations of fraud or tampering.", small))

    story.append(_p("7. Evidence references", h2))
    rows = [["Finding", "Document", "Field", "Value", "Page"]]
    for f in findings:
        if f.severity == "info":
            continue
        for e in f.evidence[:4]:
            rows.append([f.rule_id, e.get("filename", str(e.get("document_id"))), e.get("field", ""), str(e.get("value", ""))[:40], str(e.get("page") or "-")])
    if len(rows) == 1:
        rows.append(["-", "-", "-", "-", "-"])
    story.append(_table(rows, [W * 0.24, W * 0.26, W * 0.2, W * 0.2, W * 0.1], body, head))

    story.append(PageBreak())
    story.append(_p("8. Investigation timeline", h2))
    rows = [["Time (UTC)", "Action", "Resource", "Detail"]]
    for e in events[-40:]:
        rows.append([e.created_at[:19].replace("T", " "), e.action, f"{e.resource_type} {e.resource_id}", str({k: v for k, v in e.detail.items() if k not in ('sha256',)})[:80]])
    story.append(_table(rows, [W * 0.2, W * 0.2, W * 0.2, W * 0.4], body, head))

    story.append(_p("9. Human review outcome", h2))
    story.append(_p(f"Review outcome: {case.review_outcome or 'Not yet reviewed'}. Note: {case.review_note or '-'}", body))

    story.append(_p("10. Verification limitations", h2))
    for t in ["Level 1-3 checks are computed from extracted text; extraction errors can produce or hide inconsistencies. Findings involving low-confidence fields are marked and discounted.",
              "External authoritative verification (PAN, Aadhaar, GSTIN, bank records) was NOT PERFORMED: no official integration exists in this build.",
              "Cryptographic verification applies only to digitally signed files with a supplied trusted certificate; none was performed for this case unless listed above.",
              "Forensic indicators are heuristics and are labelled 'potential anomaly'; they are not proof of manipulation.",
              "Scanned or photographed documents require OCR, which is unavailable when Tesseract is not installed; such documents are reported as failed, not silently skipped.",
              "The audit log is a tamper-evident hash chain, not a blockchain; a database superuser could rewrite it."]:
        story.append(_p("- " + t, body))
    doc.build(story)
    return buf.getvalue()