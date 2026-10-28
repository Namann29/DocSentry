from __future__ import annotations

from ..identifiers import validate_pan
from ..normalize import name_similarity, surnames_match
from .base import Context, FindingDTO, ev, rule

NAME_FIELDS = {"pan_card": "name", "aadhaar": "name", "salary_slip": "employee_name",
               "employment_letter": "employee_name", "bank_statement": "account_holder"}
NOT_PERFORMED = ("Format check only; external verification with the issuing authority was NOT performed "
                 "because no authorised integration exists. A well-formed identifier proves nothing about authenticity.")


@rule("identity", requires=("pan_card",), description="PAN structure, holder-type code and surname initial")
def pan_format(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for d in ctx.of("pan_card"):
        pan = d.get("pan")
        if not pan:
            out.append(FindingDTO("identity", "identity.pan_format", 6, "medium", "PAN value not found on PAN document",
                                  "No text matching the PAN pattern was extracted; manual review needed.", [ev(d, "pan", None)]))
            continue
        chk = validate_pan(pan)
        if not chk.valid_format:
            out.append(FindingDTO("identity", "identity.pan_format", 1, "high", f"PAN {pan} is malformed",
                                  "; ".join(chk.issues), [ev(d, "pan", pan)]))
            continue
        out.append(FindingDTO("identity", "identity.pan_format", 1, "info", f"PAN {pan} is well-formed ({chk.holder_type})",
                              NOT_PERFORMED, [ev(d, "pan", pan)]))
        name = d.get("name")
        if chk.surname_initial and name:
            initial = name.split()[-1][0].upper()
            if initial != chk.surname_initial:
                out.append(FindingDTO("identity", "identity.pan_format", 2, "medium",
                                      f"PAN 5th character '{chk.surname_initial}' does not match surname initial '{initial}'",
                                      "For individual PANs the 5th character is the first letter of the surname. A mismatch can be a "
                                      "name-order convention or a PAN that does not belong to this name.",
                                      [ev(d, "pan", pan), ev(d, "name", name)]))
    return out


@rule("identity", requires=("aadhaar",), description="Aadhaar structure and Verhoeff checksum (when unmasked)")
def aadhaar_format(ctx: Context) -> list[FindingDTO]:
    out: list[FindingDTO] = []
    for d in ctx.of("aadhaar"):
        masked = d.get("aadhaar_masked")
        if not masked:
            out.append(FindingDTO("identity", "identity.aadhaar_format", 6, "medium", "Aadhaar number not found",
                                  "No masked or full Aadhaar pattern was extracted.", [ev(d, "aadhaar_masked", None)]))
            continue
        if d.get("aadhaar_checksum_valid") is None:
            out.append(FindingDTO("identity", "identity.aadhaar_format", 6, "info", f"Aadhaar shown masked ({masked}); checksum not computable",
                                  "Only the last four digits are visible, which is the expected presentation. " + NOT_PERFORMED,
                                  [ev(d, "aadhaar_masked", masked)]))
        elif d.get("aadhaar_valid_format"):
            out.append(FindingDTO("identity", "identity.aadhaar_format", 1, "info", f"Aadhaar {masked} passes structure and Verhoeff checks",
                                  "The full number was not stored; only a keyed match token. " + NOT_PERFORMED, [ev(d, "aadhaar_masked", masked)]))
        else:
            out.append(FindingDTO("identity", "identity.aadhaar_format", 1, "high", f"Aadhaar {masked} fails format/checksum",
                                  "; ".join(d.get("aadhaar_issues", [])), [ev(d, "aadhaar_masked", masked)]))
    return out


@rule("identity", description="Name consistency across all documents that carry a person name")
def name_consistency(ctx: Context) -> list[FindingDTO]:
    named = [(d, d.get(f)) for d in ctx.docs for t, f in NAME_FIELDS.items() if d.doc_type == t and d.get(f)]
    if len(named) < 2:
        return []
    ref_doc, ref = next(((d, n) for d, n in named if d.doc_type == "pan_card"), named[0])
    out: list[FindingDTO] = []
    consistent = 0
    for d, n in named:
        if d is ref_doc:
            continue
        sim = name_similarity(ref, n)
        evid = [ev(ref_doc, NAME_FIELDS[ref_doc.doc_type], ref), ev(d, NAME_FIELDS[d.doc_type], n, similarity=round(sim, 2))]
        if sim >= 0.9:
            consistent += 1
        elif sim >= 0.75 and surnames_match(ref, n):
            out.append(FindingDTO("identity", "identity.name_consistency", 3, "low", f"Name variation: '{ref}' vs '{n}'",
                                  f"Similarity {sim:.2f}; same surname. Likely initials or spelling differences; confirm manually.", evid))
        else:
            out.append(FindingDTO("identity", "identity.name_consistency", 3, "high", f"Name mismatch: '{ref}' vs '{n}'",
                                  f"Similarity {sim:.2f}. The {d.doc_type.replace('_', ' ')} names a different person than the {ref_doc.doc_type.replace('_', ' ')}.", evid))
    if consistent and not out:
        out.append(FindingDTO("identity", "identity.name_consistency", 3, "info", f"Name consistent across {consistent + 1} documents",
                              "All extracted names match within tolerance.", [ev(d, NAME_FIELDS[d.doc_type], n) for d, n in named]))
    return out


@rule("identity", requires=("pan_card", "aadhaar"), description="Date of birth agreement between PAN and Aadhaar")
def dob_consistency(ctx: Context) -> list[FindingDTO]:
    p, a = ctx.first("pan_card"), ctx.first("aadhaar")
    if not (p and a and p.get("dob") and a.get("dob")):
        return []
    if p.get("dob") != a.get("dob"):
        return [FindingDTO("identity", "identity.dob_consistency", 3, "high", f"Date of birth mismatch: {p.get('dob')} (PAN) vs {a.get('dob')} (Aadhaar)",
                           "Two identity documents disagree on the date of birth.", [ev(p, "dob", p.get("dob")), ev(a, "dob", a.get("dob"))])]
    return [FindingDTO("identity", "identity.dob_consistency", 3, "info", "Date of birth consistent between PAN and Aadhaar", "",
                       [ev(p, "dob", p.get("dob")), ev(a, "dob", a.get("dob"))])]


@rule("identity", requires=("salary_slip", "employment_letter"), description="Employer agreement between salary slip and employment letter")
def employer_consistency(ctx: Context) -> list[FindingDTO]:
    s, l = ctx.first("salary_slip"), ctx.first("employment_letter")
    se = s.get("employer")
    out: list[FindingDTO] = []
    for key in ("employer", "employer_stated"):
        le = l.get(key)
        if not (se and le):
            continue
        sim = name_similarity(se, le)
        if sim < 0.8:
            out.append(FindingDTO("identity", "identity.employer_consistency", 3, "medium", f"Employer mismatch: '{se}' (slip) vs '{le}' (letter)",
                                  f"Similarity {sim:.2f}.", [ev(s, "employer", se), ev(l, key, le)]))
            break
    if not out and se and l.get("employer"):
        out.append(FindingDTO("identity", "identity.employer_consistency", 3, "info", "Employer consistent between slip and letter", "",
                              [ev(s, "employer", se), ev(l, "employer", l.get("employer"))]))
    return out


@rule("identity", requires=("salary_slip", "bank_statement"), description="Salary slip bank account vs statement account")
def account_consistency(ctx: Context) -> list[FindingDTO]:
    s, b = ctx.first("salary_slip"), ctx.first("bank_statement")
    sa, ba = s.get("bank_account"), b.get("account_number")
    if not (sa and ba):
        return []
    sd = "".join(ch for ch in sa if ch.isdigit())[-4:]
    bd = "".join(ch for ch in ba if ch.isdigit())[-4:]
    if sd and bd and sd != bd:
        return [FindingDTO("identity", "identity.account_consistency", 3, "medium", f"Salary account ending {sd} differs from statement account ending {bd}",
                           "The salary slip names a bank account that is not the statement's account; the salary may be credited elsewhere.",
                           [ev(s, "bank_account", sa), ev(b, "account_number", "XXXX" + bd)])]
    return [FindingDTO("identity", "identity.account_consistency", 3, "info", f"Salary account ending {sd} matches statement account", "",
                       [ev(s, "bank_account", sa), ev(b, "account_number", "XXXX" + bd)])]


@rule("identity", requires=("pan_card", "salary_slip"), description="PAN on PAN document vs (masked) PAN on salary slip")
def pan_cross_check(ctx: Context) -> list[FindingDTO]:
    p, s = ctx.first("pan_card"), ctx.first("salary_slip")
    pp, sp = p.get("pan"), s.get("pan")
    if not (pp and sp):
        return []
    ok = all(a == b or b in "X*" for a, b in zip(pp, sp)) and len(pp) == len(sp)
    sev, title = ("info", "PAN on salary slip matches PAN document") if ok else ("high", f"PAN mismatch: {pp} (PAN doc) vs {sp} (salary slip)")
    return [FindingDTO("identity", "identity.pan_cross_check", 3, sev, title, "Masked characters are treated as wildcards.",
                       [ev(p, "pan", pp), ev(s, "pan", sp)])]