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
  | "REFUND_WITHOUT_ERP_REVERSAL";

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
  status: "SUPPORTED" | "UNRESOLVED";
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
