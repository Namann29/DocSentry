"""Upload validation: magic bytes, size, safe filenames, PDF safety and in-memory decryption."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from .config import settings
from .errors import InvalidInputError, PasswordRequiredError

MAGIC: list[tuple[bytes, str, set[str]]] = [
    (b"%PDF-", "application/pdf", {".pdf"}),
    (b"\x89PNG\r\n\x1a\n", "image/png", {".png"}),
    (b"\xff\xd8\xff", "image/jpeg", {".jpg", ".jpeg"}),
]
_DANGEROUS = [(re.compile(r"/Launch(?![A-Za-z0-9])"), "launch_action"),
              (re.compile(r"/JavaScript(?![A-Za-z0-9])"), "javascript"),
              (re.compile(r"/JS(?![A-Za-z0-9])"), "javascript"),
              (re.compile(r"/EmbeddedFile(?![A-Za-z0-9])"), "embedded_file"),
              (re.compile(r"/OpenAction(?![A-Za-z0-9])"), "open_action"),
              (re.compile(r"/AA(?![A-Za-z0-9])"), "additional_actions")]


def safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "upload"
    return base[:120]


def validate_upload(filename: str, data: bytes) -> tuple[str, str]:
    """Return (safe_filename, content_type) or raise InvalidInputError."""
    if not data:
        raise InvalidInputError("Empty file")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidInputError(f"File exceeds {settings.max_upload_mb} MB limit")
    safe = safe_filename(filename)
    ext = Path(safe).suffix.lower()
    for magic, ctype, exts in MAGIC:
        if data.startswith(magic):
            if ext not in exts:
                raise InvalidInputError(f"File content is {ctype} but the extension is '{ext or 'none'}'")
            return safe, ctype
    raise InvalidInputError("Unsupported or unrecognised file type (PDF, PNG and JPEG are accepted)")


@dataclass
class PdfInspection:
    data: bytes
    page_count: int
    flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    decrypted: bool = False


def inspect_pdf(data: bytes, password: str | None = None) -> PdfInspection:
    """Open in memory, authenticate if needed (password never stored), flag risky features,
    reject Launch actions, and return decrypted bytes for storage."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise InvalidInputError("Corrupt or truncated PDF") from e
    with doc:
        decrypted = False
        if doc.needs_pass:
            if not password:
                raise PasswordRequiredError("This PDF is password-protected; supply the password at upload")
            if not doc.authenticate(password):
                raise InvalidInputError("Incorrect PDF password")
            decrypted = True
        if doc.page_count == 0:
            raise InvalidInputError("PDF has no pages")
        if doc.page_count > settings.max_pages:
            raise InvalidInputError(f"PDF has {doc.page_count} pages; limit is {settings.max_pages}")
        flags: set[str] = set()
        for xref in range(1, min(doc.xref_length(), 5000)):
            try:
                obj = doc.xref_object(xref, compressed=False)
            except Exception:
                continue
            for rx, flag in _DANGEROUS:
                if rx.search(obj):
                    flags.add(flag)
        if "launch_action" in flags:
            raise InvalidInputError("PDF contains a Launch action and was rejected")
        try:
            out = doc.tobytes(encryption=fitz.PDF_ENCRYPT_NONE) if decrypted else data
        except Exception as e:
            raise InvalidInputError("Could not decrypt PDF for storage") from e
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        return PdfInspection(out, doc.page_count, sorted(flags), meta, decrypted)