<p align="center">
  <strong>DocSentry</strong><br/>
  <em>Document intelligence, forensics and investigation workspace</em>
</p>

<p align="center">
  Python 3.12 &middot; FastAPI &middot; PyMuPDF &middot; EasyOCR + Tesseract &middot; React 18 &middot; TypeScript &middot; Vite &middot; Tailwind<br/>
  63 automated tests &middot; transaction-extraction F1 1.000 on five statement layouts (two held out) &middot; black-only UI
</p>

---

## The problem

Lenders, auditors, compliance teams and HR departments receive documents they cannot trust: salary slips, bank statements, identity extracts, invoices. A modified number, a re-used invoice number, a salary slip that does not match the bank credit - each is a small edit that costs real money. Checking by eye does not scale, and a tool that shouts "FRAUD" on a heuristic is worse than no tool at all.

## What DocSentry does

DocSentry treats documents like evidence. It answers three questions, with the page, field and rule behind every answer:

| Question | How |
|---|---|
| **Has this document been modified?** | PDF structure (re-saves after creation, JavaScript, embedded files, open actions), metadata consistency, numbers set in a font family different from the page |
| **Does it agree with itself?** | Running-balance reconciliation with repair candidates, salary arithmetic, GST line and tax maths, PAN structure, Aadhaar Verhoeff checksum, GSTIN check digit |
| **Does it agree with the other documents?** | Salary slip vs bank credit, invoice vs purchase order vs payment, duplicate invoice numbers with different totals, name / date of birth / employer / account across documents |

The result is a **risk outcome a reviewer can defend**: *Low observed risk*, *Review recommended*, *High observed risk*, or *Insufficient evidence* - plus a PDF report with every contribution listed and a limitations section.

### Design principle: every check says how much it proves

| Level | Meaning | Example |
|---|---|---|
| 1 | Format validation | PAN is 5 letters, 4 digits, 1 letter |
| 2 | Internal consistency | Row 14's balance follows from row 13 |
| 3 | Cross-document consistency | Slip net pay equals the salary credit that month |
| 4 | Cryptographic verification | A signature verifies against a trusted certificate |
| 5 | External authoritative verification | Confirmed by the issuing authority - **not performed**, and marked so everywhere |
| 6 | Suspicious indicator / unverified | A heuristic flag or an item nobody has checked |

A valid checksum means *well-formed*, not *genuine*. A font mismatch is a *potential modification*, not proof. Agreement between documents does not establish authenticity. The interface, the API and the report all say this.

## Highlights

- **Document security scan** - drop any PDF or image: fingerprint, structure, metadata, modification indicators and masked identifiers, each row with its reason, and "Not checked" with the reason when a check cannot run.
- **Tamper heat-map** - amber boxes in the viewer on numbers whose font differs from the page, at exact PDF coordinates.
- **Header-independent table inference** - bank-statement tables are rebuilt from where amounts align and which debit/credit assignment makes the balance reconcile; a layout no rule was written for still parses, and a wrong inference is rejected rather than reported.
- **OCR for photos and scans** - EasyOCR (deep-learning detector + recogniser) with Tesseract as a second opinion per region, OpenCV preprocessing, deskew, a quality gate, per-word confidence, and position-aware repair of OCR confusions in identifiers (an `O` read as `0` in a PAN).
- **Sensitive-information detection** - PAN, Aadhaar (with checksum), GSTIN, IFSC, account, phone, email - shown masked; the unmasked value is never stored.
- **Explainable risk** - fixed points per severity under a versioned policy, halved when the involved extraction is low-confidence, capped at 100; evidence coverage = checks evaluated / checks applicable; too little evidence yields *Insufficient evidence*, never *Low risk*.
- **Extraction review** - correct any field; the original is kept, the correction rate is measured, and the case re-runs on the corrected values.
- **Tamper-evident audit log** - append-only, hash-linked rows guarded by a database trigger; verifiable on demand. (Tamper-evident, not a blockchain: a database superuser could rewrite it, and the documentation says so.)
- **Honest capability reporting** - `/api/health` and the Settings page list what is available; unavailable features are shown as unavailable, never simulated.

## What is AI here, and what is not

- **Learned**: text recognition for images - EasyOCR's CRAFT detector and CRNN recogniser, and Tesseract's LSTM. Pre-trained models; input an image, output text regions with confidences.
- **Deterministic**: everything built on that text - classification, extraction, checksums, arithmetic, cross-document rules, forensic indicators and scoring. Rules and algorithms, reproducible, traceable.
- **Absent**: no generative model, no model decides a score, no external AI service is called.

## Architecture

```
Upload -> Validate -> Extract (native text | OCR ensemble) -> Normalise -> Classify -> Parse
       -> Security scan -> Rule engines (identity | financial | cross-document | forensics) -> Risk policy -> Report
```

```
backend/app/
  upload.py            magic-byte type check, size limit, safe names, PDF inspection, in-memory decryption
  ingest.py            single entry point for uploads, demo scenarios and quick scans
  extraction/          pymupdf_adapter (word boxes), tables (geometry), infer_table (header-independent, arithmetic-validated),
                       ocr_adapter (Tesseract), easyocr_adapter, ensemble_adapter, classifier (keyword + structure, abstains)
  parsers/             bank statement, salary slip, GST invoice, purchase order, employment letter, PAN, Aadhaar
  security_scan.py     structure, metadata, font consistency, masked identifiers, versioned security score
  engines/             rule registry; identity, financial, cross_document, forensics rules with evidence
  risk.py              points policy, thresholds, evidence coverage, insufficient-evidence reasons
  audit.py             hash-linked append-only log, chain verification
  report.py            ReportLab investigation report
  routers/             auth, cases, documents, processing, scan, demo, audit
frontend/src/
  pages/               Landing, Overview, Scan, Compare (unavailable state), Investigate, Cases, case/* (Summary, Upload, Documents,
                       DocumentViewer, ExtractionReview, FindingsHub, Financial, EvidenceGraph, Forensics, Risk, Vault, Reports), Audit, Settings
```

## Quick start (Windows)

Prerequisites: Python 3.12, Node 20+, optionally Tesseract (`winget install UB-Mannheim.TesseractOCR`).

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Then, in two terminals:

```powershell
cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev
```

Open http://localhost:5173. The first administrator comes from `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `backend/.env` (copied from `.env.example` by setup). API docs: http://localhost:8000/docs.

Optional OCR for photos and scans: `pip install -r backend/requirements-ocr.txt` (pulls PyTorch; models download on first use). `/api/health` reports the active engine (`ensemble`, `easyocr`, `tesseract` or none).

## Five-minute demo

1. **Scan a document** -> `backend/corpus/out/demo_set/payslip_oct_2026_received.pdf`: the edited amount lights up in a different font, plus one re-save. **View document** shows the amber box.
2. Scan `payslip_oct_2026_email_attachment.pdf`: a JavaScript open action, flagged (never executed).
3. Scan `kyc_details_form.pdf`: Aadhaar, PAN, phone and email found and shown masked.
4. Scan `payslip_oct_2026.pdf`: the clean control - every check passes or says why it could not run.
5. **Salary slip vs statement -> Try a sample case -> Salary vs bank mismatch**: seven synthetic documents, uploaded under generic names, run through the standard pipeline; the summary shows the Rs 65,000 vs Rs 45,000 discrepancy; click the amount to open the statement at that credit. **Risk breakdown** lists every point; **Download report** produces the PDF.

## Evaluation

```powershell
cd backend
python -m pytest -q            # 63 tests
python corpus\benchmark.py     # transaction-level precision / recall / F1 per statement layout
```

| Layout | Set | F1 before inference | F1 after inference |
|---|---|---|---|
| 1-3 | development | 1.000 | 1.000 |
| 4 | held out | 1.000 | 1.000 |
| 5 | held out | 0.000 | 1.000 |

Parsers were developed on layouts 1-3 only. Layout 5 (single signed amount column, ISO dates, `#` serial) failed completely until header-independent inference was added - the failure, and the fix, are both reported.

Also verified by tests: tamper detection on a programmatically modified payslip; OCR on rendered synthetic images including deskew and PAN character repair; the five scenario outcomes (expected results live only in the tests); the audit chain detecting a tampered row; states that must stay distinguishable (not yet analysed, analysed with nothing found, weakly classified, unsupported, failed).

## Data and ethics

There is no public dataset of Indian KYC documents, and there must not be one - they are personal data. DocSentry's evaluation therefore rests on:

- a **synthetic corpus generator** (`backend/corpus/generate.py`) with known ground truth: five statement layouts, two payslip layouts, invoices, purchase orders, letters, PAN and Aadhaar extracts, controlled discrepancies and a tampered variant (`make_tampered.py`, `make_demo_set.py`);
- **public scan datasets** (SROIE, FUNSD, CORD) for OCR robustness and classifier abstention;
- a **local batch check** (`backend/corpus/scan_folder.py`) for a user's own documents - nothing is uploaded or stored.

Generated documents carry a small "specimen for software testing" footer and imitate no official design. Do not upload real identity documents to a demo instance.

## API overview

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/login`, `GET /api/auth/me` | JWT auth; roles admin / analyst / reviewer / viewer, one authorization choke point |
| `POST /api/cases`, `GET /api/cases/{id}` | cases (owner-scoped) |
| `POST /api/cases/{id}/documents` | multi-file upload with optional PDF password |
| `POST /api/cases/{id}/process?engines=` | run the pipeline; `engines` enables the single-document vs cross-document ablation |
| `GET /api/cases/{id}/findings`, `/risk`, `/report.pdf` | findings with evidence, risk breakdown, PDF report |
| `POST /api/scan` | quick scan: one file, its own case, full analysis |
| `GET /api/documents/{id}/security`, `/pages/{n}`, `/fields` | security scan, page image, extracted fields; `PATCH .../fields/{id}` corrects a field |
| `POST /api/demo/scenarios/{n}` | synthetic scenario through the standard pipeline |
| `GET /api/audit/events`, `/verify` | audit log and chain verification |

## Limitations

- Verification with issuing authorities is not performed; a clean result is not a statement of authenticity.
- Font and re-save indicators are heuristics; an editor that matches the font and saves a fresh copy leaves them nothing to see.
- Statements without a running-balance column are rejected by the inference rather than guessed.
- OCR quality depends on the image; blurry or heavily compressed photos read partially, and the quality gate says so.
- Not implemented: version comparison, retrieval-based assistant, AWS integrations, asynchronous job queue. Shown as unavailable, never simulated.

## Repository layout

```
backend/      FastAPI application, parsers, engines, tests, corpus generator, benchmark
frontend/     React application
scripts/      setup script
STATUS.md     what runs, what is tested, what is unverified
DECISIONS.md  assumptions and trade-offs
```
