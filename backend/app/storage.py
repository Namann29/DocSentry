"""Storage backends. Local filesystem now; S3 behind the same interface in AWS mode."""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .config import settings
from .errors import InvalidInputError, NotFoundError


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, suffix: str) -> str:
        """Store bytes, return an opaque object name."""

    @abstractmethod
    def read(self, name: str) -> bytes: ...

    @abstractmethod
    def delete(self, name: str) -> None: ...

    @abstractmethod
    def local_path(self, name: str) -> Iterator[Path]:
        """Context manager yielding a filesystem path (S3 will download to a temp file)."""


class LocalStorage(StorageBackend):
    def __init__(self, base: Path) -> None:
        self.base = base.resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise InvalidInputError("Invalid object name")
        p = (self.base / name).resolve()
        if p.parent != self.base:
            raise InvalidInputError("Path traversal rejected")
        return p

    def save(self, data: bytes, suffix: str) -> str:
        name = f"{uuid.uuid4().hex}{suffix if re.fullmatch(r'\.[a-z0-9]{1,5}', suffix) else ''}"
        self._path(name).write_bytes(data)
        return name

    def read(self, name: str) -> bytes:
        p = self._path(name)
        if not p.exists():
            raise NotFoundError("Stored object missing")
        return p.read_bytes()

    def delete(self, name: str) -> None:
        p = self._path(name)
        if p.exists():
            p.unlink()

    @contextmanager
    def local_path(self, name: str) -> Iterator[Path]:
        p = self._path(name)
        if not p.exists():
            raise NotFoundError("Stored object missing")
        yield p


def get_storage() -> StorageBackend:
    """Dependency injection point; AWS mode will return an S3 backend here."""
    return LocalStorage(settings.storage_dir)