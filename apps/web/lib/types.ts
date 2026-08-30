export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type ExceptionStatus = "OPEN" | "IN_REVIEW" | "RESOLVED" | "ESCALATED";
export type ReconciliationStatus = "RECONCILED" | "RECONCILED_WITH_VARIANCE" | "EXCEPTION" | "AMBIGUOUS" | "PENDING";

export type ExceptionType =
  | "REFUND_WITHOUT_INVENTORY_RETURN"
  | "MISSING_SETTLEMENT"
  | "DUPLICATE_PAYMENT"
  | "ERP_INVOICE_MISSING"
  | "ERP_AMOUNT_MISMATCH"
  | "SETTLEMENT_TIMING"
  | "MANUAL_WORKFLOW_ANOMALY"
  | "REFUND_WITHOUT_ERP_REVERSAL"
  | "PARTIAL_REFUND_MISMATCH"
  | "SETTLEMENT_FEE_VARIANCE"
  | "AMBIGUOUS_ASSOCIATION";

export interface Metric {
  label: string;
  value: string;
  detail: string;
  trend?: string;
  tone?: "positive" | "warning" | "neutral" | "critical";
}

export interface ExceptionItem {
  id: string;
  orderId: string;
  type: ExceptionType;
  label: string;
  severity: Severity;
  status: ExceptionStatus;
  exposure: number;
  currency: "INR";
  detectedAt: string;
  summary: string;
  source: string;
  ruleCount: number;
  assignee?: string;
  pattern?: string;
}

export interface TimelineEvent {
  time: string;
  title: string;
  detail: string;
  source: string;
  state: "complete" | "missing" | "warning";
}

export interface EvidenceItem {
  source: string;
  recordId?: string;
  fact: string;
  tone: "positive" | "warning" | "neutral";
}

export interface Investigation {
  status: "SUPPORTED" | "UNRESOLVED" | "FAILED";
  rootCause: string;
  rootCauseCode: string;
  summary: string;
  evidenceScore: number;
  supportingEvidence: EvidenceItem[];
  contradictoryEvidence: EvidenceItem[];
  missingEvidence: string[];
  action: string;
  actionCode: string;
  requiresHumanReview: boolean;
  tools: { name: string; target: string; duration: string }[];
}

export interface LifecycleRecord {
  id: string;
  source: string;
  status: "confirmed" | "missing" | "warning";
  amount?: string;
  detail: string;
}

export interface ExceptionDetail extends ExceptionItem {
  lifecycle: LifecycleRecord[];
  timeline: TimelineEvent[];
  investigation: Investigation;
  policy: { owner: string; reason: string; state: string };
  audit: { time: string; actor: string; action: string; detail: string }[];
}

export interface Pattern {
  id: string;
  title: string;
  description: string;
  incidents: number;
  exposure: number;
  location: string;
  control: string;
  severity: Severity;
}

export interface ApiPattern {
  pattern_id: string;
  exception_type: string;
  title: string;
  occurrence_count: number;
  associated_exposure: number | string;
  currency: string;
  location: string;
  workflow: string;
  observation: string;
  prevention_recommendation: string;
  severity: Severity;
  member_order_ids: string[];
}

export interface ApiAuditEvent {
  event_id: string;
  organization_id: string;
  actor_id: string;
  action: string;
  resource_id: string;
  correlation_id: string;
  created_at: string;
}

export interface ApiEvaluation {
  evaluation_id: string;
  organization_id: string;
  seed: number;
  anomaly_rate: number;
  report: {
    lifecycles: number;
    auto_reconciled: number;
    exceptions: number;
    ambiguous: number;
    match_rate: number;
    match_precision: number;
    exception_recall: number;
    throughput_per_second: number;
    unresolved_exceptions: number;
  };
  created_at: string;
}

export interface ApiDashboardSummary {
  organization_id: string;
  reconciliation_run_id: string;
  lifecycle_count: number;
  auto_reconciled_count: number;
  exception_count: number;
  open_exposure: number | string;
  requires_review_count: number;
  generated_at: string;
}

export interface ApiExceptionSummary {
  id: string;
  organization_id: string;
  order_id: string;
  type: ExceptionType;
  severity: Severity;
  status: ExceptionStatus;
  financial_exposure: number | string;
  currency: string;
  detected_at: string;
  rules_triggered: string[];
}

export interface ApiInvestigation {
  investigation_id: string;
  exception_id: string;
  status: "SUPPORTED" | "UNRESOLVED" | "FAILED";
  root_cause_code: string | null;
  summary: string;
  supporting_evidence: { source: string; record_id?: string | null; fact: string }[];
  contradictory_evidence: { source: string; record_id?: string | null; fact: string }[];
  missing_evidence: string[];
  recommended_action_code: string | null;
  requires_human_review: boolean;
  evidence_score: number;
  tool_calls: { name: string; target: string; status: string; duration_ms: number }[];
  created_at: string;
}
