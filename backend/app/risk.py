"""Transparent, versioned risk policy. Every point is attributable to a finding; no opaque scores."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from .engines.base import LEVEL_NAMES, CheckStatus, DocView, FindingDTO

POLICY_VERSION = "1.0"
POINTS = {"info": 0, "low": 5, "medium": 15, "high": 30}
EXTRACTION_ERROR_FACTOR = 0.5
THRESHOLDS = {"high": 50, "review": 15}
MIN_DOCS = 2
MIN_COVERAGE = 0.5


def points_for(f: FindingDTO) -> int:
    base = POINTS.get(f.severity, 0)
    return int(base * EXTRACTION_ERROR_FACTOR) if f.possible_extraction_error else base


@dataclass
class RiskResult:
    score: int
    outcome: str
    coverage: float
    extraction_quality: float
    breakdown: dict[str, Any]


def assess(findings: list[FindingDTO], checks: list[CheckStatus], views: list[DocView], failed: int) -> RiskResult:
    applicable = [c for c in checks if c.status != "not_applicable"]
    evaluated = [c for c in applicable if c.status == "evaluated"]
    coverage = round(len(evaluated) / len(applicable), 3) if applicable else 0.0
    confs = [c for v in views for c in v.conf.values()]
    quality = round(mean(confs), 3) if confs else 0.0
    contributions = [{"rule_id": f.rule_id, "title": f.title, "severity": f.severity, "level": f.level,
                      "level_name": LEVEL_NAMES[f.level], "points": points_for(f),
                      "extraction_discounted": f.possible_extraction_error} for f in findings]
    raw = sum(c["points"] for c in contributions)
    score = min(100, raw)
    if not views:
        outcome = "Processing failed" if failed else "Insufficient evidence"
    elif len(views) < MIN_DOCS or coverage < MIN_COVERAGE:
        outcome = "Insufficient evidence"
    elif score >= THRESHOLDS["high"]:
        outcome = "High observed risk"
    elif score >= THRESHOLDS["review"]:
        outcome = "Review recommended"
    else:
        outcome = "Low observed risk"
    breakdown = {
        "policy_version": POLICY_VERSION, "points_table": POINTS, "extraction_error_factor": EXTRACTION_ERROR_FACTOR,
        "thresholds": THRESHOLDS, "raw_points": raw, "capped_score": score, "contributions": contributions,
        "checks": [{"rule_id": c.rule_id, "engine": c.engine, "description": c.description, "status": c.status, "findings": c.findings} for c in checks],
        "documents_processed": len(views), "documents_failed": failed,
        "insufficient_reason": (f"{len(views)} document(s) processed (policy minimum {MIN_DOCS}); evidence coverage {coverage:.0%} (minimum {MIN_COVERAGE:.0%})"
                                if outcome == "Insufficient evidence" else None),
        "external_verification": "NOT_PERFORMED",
        "notes": ["Outcome is an investigation recommendation, not a fraud judgement.",
                  "Heuristic findings are potential anomalies, never proof of manipulation.",
                  "Evidence coverage = evaluated checks / applicable checks; low coverage yields 'Insufficient evidence'."],
    }
    return RiskResult(score, outcome, coverage, quality, breakdown)