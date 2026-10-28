"""Rule registry shared by all engines. Rules are pure functions over DocViews."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

log = logging.getLogger("docsentry.engines")

LEVEL_NAMES = {1: "Format validation", 2: "Internal consistency", 3: "Cross-document consistency",
               4: "Cryptographic verification", 5: "External authoritative verification",
               6: "Suspicious indicator / unverified"}


@dataclass
class DocView:
    id: int
    doc_type: str
    filename: str
    data: dict[str, Any]
    conf: dict[str, float] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def amount(self, key: str) -> Decimal | None:
        v = self.data.get(key)
        try:
            return Decimal(str(v)) if v not in (None, "") else None
        except InvalidOperation:
            return None

    def confidence(self, name: str, default: float = 0.95) -> float:
        return self.conf.get(name, default)


@dataclass
class FindingDTO:
    engine: str
    rule_id: str
    level: int
    severity: str  # info | low | medium | high
    title: str
    explanation: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    possible_extraction_error: bool = False


@dataclass
class Context:
    docs: list[DocView]

    def of(self, doc_type: str) -> list[DocView]:
        return [d for d in self.docs if d.doc_type == doc_type]

    def first(self, doc_type: str) -> DocView | None:
        ds = self.of(doc_type)
        return ds[0] if ds else None


@dataclass
class RuleSpec:
    id: str
    engine: str
    requires: tuple[str, ...]
    description: str
    fn: Callable[[Context], list[FindingDTO]]


@dataclass
class CheckStatus:
    rule_id: str
    engine: str
    description: str
    status: str  # evaluated | not_applicable | error
    findings: int = 0


RULES: dict[str, RuleSpec] = {}


def rule(engine: str, requires: tuple[str, ...] = (), description: str = ""):
    """Decorator registering a rule as '<engine>.<function name>'."""
    def deco(fn: Callable[[Context], list[FindingDTO]]):
        rid = f"{engine}.{fn.__name__}"
        RULES[rid] = RuleSpec(rid, engine, requires, description or (fn.__doc__ or "").strip(), fn)
        return fn
    return deco


def ev(doc: DocView, field_name: str, value: Any, page: int | None = None, **extra: Any) -> dict[str, Any]:
    return {"document_id": doc.id, "doc_type": doc.doc_type, "filename": doc.filename, "field": field_name,
            "value": None if value is None else str(value), "page": page, **extra}


def run_engines(docs: list[DocView], engines: set[str] | None = None) -> tuple[list[FindingDTO], list[CheckStatus]]:
    ctx = Context(docs)
    present = {d.doc_type for d in docs}
    findings: list[FindingDTO] = []
    checks: list[CheckStatus] = []
    for spec in RULES.values():
        if engines is not None and spec.engine not in engines:
            continue
        if not set(spec.requires) <= present:
            checks.append(CheckStatus(spec.id, spec.engine, spec.description, "not_applicable"))
            continue
        try:
            out = spec.fn(ctx)
            findings.extend(out)
            checks.append(CheckStatus(spec.id, spec.engine, spec.description, "evaluated", len(out)))
        except Exception:  # a broken rule must never hide the others; it is reported, not swallowed
            log.exception("rule %s failed", spec.id)
            checks.append(CheckStatus(spec.id, spec.engine, spec.description, "error"))
    return findings, checks