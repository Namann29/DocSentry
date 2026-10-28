from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    email: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    email: Email
    password: str = Field(min_length=10)
    role: str = Field(pattern="^(admin|analyst|reviewer|viewer)$")


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    case_type: str = "general"
    description: str = ""


class CaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(open|processing|reviewed|closed)$")


class CaseOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    title: str
    case_type: str
    description: str
    status: str
    owner_id: int
    risk_outcome: str
    risk_score: int
    evidence_coverage: float
    extraction_quality: float
    review_outcome: str | None
    review_note: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    finding_count: int = 0


class AuditEventOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    action: str
    resource_type: str
    resource_id: str
    actor_id: int | None
    detail: dict[str, Any]
    created_at: str
    hash: str
    prev_hash: str


class FieldOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    value: str
    normalized_value: str
    confidence: float
    page: int
    bbox: list[float] | None
    snippet: str
    method: str
    corrected: bool
    original_value: str | None


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    case_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    page_count: int
    doc_type: str
    classification_confidence: float
    extraction_method: str
    status: str
    error_message: str
    security_flags: list[str]
    created_at: datetime


class DocumentDetail(DocumentOut):
    parsed: dict[str, Any] | None
    pdf_metadata: dict[str, Any] | None
    fields: list[FieldOut]


class FieldCorrection(BaseModel):
    value: str = Field(min_length=1, max_length=500)
    normalized: str | None = None


class FindingOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    engine: str
    rule_id: str
    level: int
    severity: str
    title: str
    explanation: str
    evidence: list[dict[str, Any]]
    points: int
    possible_extraction_error: bool


class ProcessOut(BaseModel):
    job_id: int
    documents: int
    processed: int
    failed: list[str]
    findings: int
    risk_score: int
    risk_outcome: str
    evidence_coverage: float


class JobOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    case_id: int
    kind: str
    status: str
    progress: int
    message: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RiskOut(BaseModel):
    score: int
    outcome: str
    evidence_coverage: float
    extraction_quality: float
    breakdown: dict[str, Any]


class ReviewRequest(BaseModel):
    outcome: str = Field(pattern="^(cleared|escalate|needs_more_evidence|rejected)$")
    note: str = ""


class ExtractionStats(BaseModel):
    fields: int
    corrected: int
    correction_rate: float
    mean_confidence: float