# DocSentry - STATUS

Verified on Windows 11, Python 3.12.10, Node 22 (2026-10-28): python -m pytest -q -> 63 passed; npm run build -> clean; corpus\benchmark.py -> F1 1.000 on all five statement layouts (two held out).

## Runs and is tested
- Upload validation, PDF inspection, in-memory decryption; SHA-256 fingerprints; local storage with path-traversal protection.
- Native PDF extraction with word coordinates; geometry table reconstruction; header-independent inference validated by balance arithmetic.
- OCR: EasyOCR + Tesseract ensemble with preprocessing, deskew, quality gate, per-word confidence, position-aware PAN repair.
- Parsers: bank statement, salary slip, GST invoice, purchase order, employment letter, PAN, Aadhaar (masked only).
- Security scan: incremental updates, metadata consistency, mixed-font numeric values, masked identifier exposure, versioned score.
- Engines: identity, financial (running balance with repair candidates), cross-document, forensics.
- Risk policy v1.0 with evidence coverage and explained insufficient evidence; weakly classified documents excluded from type-specific rules.
- Audit log: append-only, hash-linked, DB trigger, chain verification.
- PDF report; demo scenarios through the same pipeline; quick scan; document-type portals.
- Frontend: landing page, overview, scan, investigations, viewer with amber overlays, extraction review, findings, graph, risk, vault, report, audit, settings.

## Not implemented (shown as unavailable)
- Version comparison, retrieval-based assistant, AWS (S3, Lambda, CloudWatch, Textract, Bedrock), Celery/SSE jobs, Playwright E2E, Alembic migration files.

## Known limitations
- Heuristic indicators are potential anomalies, not proof; external authority verification is not performed.
- OCR on blurry or heavily compressed photos reads partially; the quality gate and confidences say so.
- Linearised PDFs count as one incremental update.