# DECISIONS

- 2026-10-28 Env audit: Python 3.12.10, Node 22.14, Docker CLI present but engine not running, Tesseract absent, no local Postgres/Redis, 16 GB RAM.
- SQLite first via SQLAlchemy 2 + Alembic; PostgreSQL by changing DATABASE_URL (triggers have both dialects).
- In-process job runner first; Celery/Redis later behind the same interface.
- Extraction ladder rungs 1-2 (PyMuPDF native text + geometry tables) before OCR.
- Admin user seeded from .env on first start; all other users created by admin (no self-assigned roles).
- Audit log: tamper-evident hash chain + append-only trigger. Not a blockchain. Superuser could rewrite; CloudWatch witness in AWS mode.- Security score policy 1.0 (security_scan.TABLE): points per indicator with caps; sensitive-information exposure contributes to the per-document security score but only unmasked Aadhaar contributes to the case risk, because a statement showing its own account number is expected, not anomalous.
- Font-consistency check compares font FAMILY (bold/italic variants of the body font are legitimate) and only on text containing digits or currency, excluding page margins (banners, page numbers).
- Security score policy 1.0: points per indicator with caps; PII exposure counts in the per-document security score, but only unmasked Aadhaar contributes to the case risk.
- Font check compares font FAMILY, only for text containing digits/currency, excluding page margins (banners, page numbers).
