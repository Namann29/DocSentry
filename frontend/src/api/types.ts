export interface User { id: number; email: string; role: "admin" | "analyst" | "reviewer" | "viewer"; is_active: boolean }
export interface Case {
  id: number; title: string; case_type: string; description: string; status: string; owner_id: number;
  risk_outcome: string; risk_score: number; evidence_coverage: number; extraction_quality: number;
  review_outcome: string | null; review_note: string; created_at: string; updated_at: string;
  document_count: number; finding_count: number;
}
export interface Doc {
  id: number; case_id: number; original_filename: string; content_type: string; size_bytes: number; sha256: string;
  page_count: number; doc_type: string; classification_confidence: number; extraction_method: string; status: string;
  error_message: string; security_flags: string[]; created_at: string;
}
export interface Field {
  id: number; name: string; value: string; normalized_value: string; confidence: number; page: number;
  bbox: number[] | null; snippet: string; method: string; corrected: boolean; original_value: string | null;
}
export interface DocDetail extends Doc { parsed: Record<string, any> | null; pdf_metadata: Record<string, any> | null; fields: Field[] }
export interface Evidence { document_id: number; doc_type: string; filename: string; field: string; value: string | null; page: number | null; [k: string]: any }
export interface Finding {
  id: number; engine: string; rule_id: string; level: number; severity: "info" | "low" | "medium" | "high";
  title: string; explanation: string; evidence: Evidence[]; points: number; possible_extraction_error: boolean;
}
export interface Risk { score: number; outcome: string; evidence_coverage: number; extraction_quality: number; breakdown: Record<string, any> }
export interface Job { id: number; case_id: number; kind: string; status: string; progress: number; message: string; created_at: string; started_at: string | null; finished_at: string | null }
export interface ProcessResult { job_id: number; documents: number; processed: number; failed: string[]; findings: number; risk_score: number; risk_outcome: string; evidence_coverage: number }
export interface AuditEvent { id: number; action: string; resource_type: string; resource_id: string; actor_id: number | null; detail: Record<string, any>; created_at: string; hash: string; prev_hash: string }
export interface Health { status: string; run_mode: string; version: string; rules: number; capabilities: Record<string, boolean> }
export interface Rule { id: string; engine: string; requires: string[]; description: string }
export interface ExtractionStats { fields: number; corrected: number; correction_rate: number; mean_confidence: number }

export const LEVEL_NAMES: Record<number, string> = {
  1: "Format validation", 2: "Internal consistency", 3: "Cross-document consistency",
  4: "Cryptographic verification", 5: "External authoritative verification", 6: "Suspicious indicator / unverified",
};
export const DOC_TYPE_LABEL: Record<string, string> = {
  bank_statement: "Bank statement", salary_slip: "Salary slip", invoice: "Invoice", purchase_order: "Purchase order",
  employment_letter: "Employment letter", pan_card: "PAN", aadhaar: "Aadhaar", unknown: "Unknown",
};
export const inr = (v: string | number | null | undefined) =>
  v === null || v === undefined || v === "" ? "-" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 }).format(Number(v));
export interface Contribution { check: string; category: "structure" | "modification" | "metadata" | "sensitive"; title: string; explanation: string; points: number; page?: number; bbox?: number[]; value?: string; field?: string }
export interface ModificationIndicator { page: number; text: string; font: string; size: number; bbox: number[]; dominant_font: string }
export interface SensitiveItem { kind: string; masked: string; page: number; bbox: number[] }
export interface SecurityScan {
  version: string; fingerprint: { sha256: string; size_bytes: number; content_type: string };
  structure: Record<string, any>; metadata: { producer: string | null; creator: string | null; created: string | null; modified: string | null; title?: string | null; author?: string | null; issues: string[] };
  fonts: { pages: { page: number; fonts: Record<string, number>; dominant_font: string | null }[]; mixed_font_words: ModificationIndicator[] };
  modification_indicators: ModificationIndicator[]; sensitive: SensitiveItem[];
  score: number; level: string; thresholds: Record<string, number>; contributions: Contribution[]; not_checked: { check: string; reason: string }[]; note: string;
}
export interface ScanResponse { case_id: number; document_id: number; filename: string; doc_type: string; status: string; error_message: string; page_count: number; extraction_method?: string; scan: SecurityScan | null; ocr_quality?: Record<string, any>[] | null; fields?: Record<string, any>; classification_confidence?: number; weak_parse?: boolean; warnings?: string[]; expected_type?: string | null; type_assumed?: boolean; type_mismatch?: boolean }
