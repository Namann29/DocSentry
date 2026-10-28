# DocSentry STATUS

## Implemented (verify with `python -m pytest -q`)
- Batch 1: config, SQLite/SQLAlchemy 2, auth (bcrypt+SHA-256 prehash, JWT, lockout), single authorization choke point, cases CRUD, hash-linked append-only audit log with DB trigger and chain verification, structured errors.
- Batch 2: extraction ladder rungs 1-2 (PyMuPDF word boxes, geometry table reconstruction), classifier with abstention, parsers (bank statement, salary slip, GST invoice, PO, employment letter, PAN, Aadhaar), identifiers (PAN, Verhoeff, GSTIN), Indian amount/date/name normalisers, synthetic corpus generator (5 statement templates, 2 slip layouts), extraction benchmark with held-out templates.
- Batch 3: storage backend (local), upload validation (magic bytes, size, safe names, PDF JS/Launch/embedded-file flags, in-memory password decryption), documents API (upload, list, detail, page image, download, fields, correction, soft delete), case pipeline, identity/financial/cross-document engines (rule registry), transparent risk policy v1.0 with evidence coverage, ReportLab investigation report, demo scenarios through the same pipeline, scenario tests with expected results only in tests, ablation switch (`engines=` query).

## Not implemented yet
- Frontend (Batch 4). Forensics engine, evidence graph, vault retention/purge (Batch 5). Async jobs/SSE/Celery, OCR/multiprocessing benchmark, RAG assistant (Batch 5/6). AWS (Batch 6). Playwright E2E (Batch 7).
- Salary slip layouts 3-4 and invoice layouts 2-4 in the corpus generator; image perturbations (need OpenCV + Tesseract).
- Rate limiting; Alembic migration file (autogenerate instructions in README); Postgres advisory lock for the audit chain.

## Known limitations
- OCR unavailable: image/scanned documents are reported as failed, never silently processed.
- Supplier/vendor payment matching is token-based on the description; descriptions without recognisable tokens will not match.
- Invoice buyer/supplier GSTIN assignment assumes supplier GSTIN appears first.
- Benchmark numbers on held-out templates 4-5 are whatever `corpus\benchmark.py` prints; report them as measured.
## Batch 5a: document security scan (UNVERIFIED until pytest passes)
- `security_scan.py`: incremental-update count, metadata date/producer checks, mixed-font numeric words (margins ignored), masked PII exposure, versioned score table.
- Forensics rule feeds the case risk; PDF report has a security section. `GET /documents/{id}/security`, `POST /scan` (quick scan through the normal ingest path).
- `corpus/make_tampered.py` produces a demo file with a replaced net pay in Courier and an incremental save.
- Known limits: linearised PDFs count as one incremental update; the font heuristic ignores non-numeric text and page margins to limit false positives; no OCR means scanned files get structure/metadata checks only.

## Batch 5a: document security scan (UNVERIFIED until pytest passes)
- security_scan.py: incremental-update count, metadata checks, mixed-font numeric words (margins ignored), masked PII exposure, versioned score table.
- Forensics rule feeds the case risk; PDF report has a security section. GET /documents/{id}/security, POST /scan.
- corpus/make_tampered.py produces a demo file with a replaced net pay in Courier and an incremental save.

## OCR rung (UNVERIFIED until test_ocr.py runs with Tesseract installed)
- Images and scanned PDFs: render at 300 dpi -> OpenCV denoise/deskew/adaptive threshold -> Tesseract word boxes + confidences -> same classifier, parsers, scan and masking.
- Quality gate per page (blur, contrast, brightness, resolution) stored in parsed._ocr_quality; low word confidence propagates to findings.
- Limits: English only (`OCR_LANGS=eng+hin` after installing the Hindi pack); real ID-card photos with holograms are noisy; font-consistency check is unavailable for OCR input.
