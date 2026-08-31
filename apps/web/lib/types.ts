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
  currency: string;
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

export interface ApiLifecycleGraph {
  exception_id: string;
  organization_id: string;
  nodes: { id: string; entity_type: string; label: string; state: "CONFIRMED" | "MISSING"; amount_minor?: number | null }[];
  edges: { source: string; target: string; relationship: string }[];
}

export interface ApiLifecycleResponse {
  organization_id: string;
  order: Record<string, unknown>;
  payments: Record<string, unknown>[];
  settlements: Record<string, unknown>[];
  invoices: Record<string, unknown>[];
  refunds: Record<string, unknown>[];
  inventory_movements: Record<string, unknown>[];
  employee_actions: Record<string, unknown>[];
}

export type ResolutionActionCode = "REQUEST_INVENTORY_VERIFICATION" | "REQUEST_ERP_INVOICE_CORRECTION" | "REQUEST_PAYMENT_REVIEW" | "REQUEST_SETTLEMENT_REVIEW" | "REQUEST_REFUND_REVIEW" | "MARK_AS_TIMING_DIFFERENCE" | "MARK_AS_EXPECTED_FEE_VARIANCE" | "ESCALATE_TO_FINANCE_MANAGER" | "ESCALATE_TO_CONTROLLER" | "CLOSE_AS_RESOLVED";

export interface ApiResolutionRequest {
  request_id: string;
  exception_id: string;
  action_code: ResolutionActionCode;
  status: "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
  financial_exposure: number | string;
  currency: string;
  required_capability: string;
  required_approvals: number;
  approvals_received: number;
  requester_id: string;
  created_at: string;
}

export interface EvaluationRunRequest {
  orders: number;
  seed: number;
  anomaly_rate: number;
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

export type FinancialInvestigationStatus = "DRAFT" | "SOURCES_UPLOADED" | "MAPPING_REQUIRED" | "RELATIONSHIP_REVIEW" | "READY_TO_BUILD" | "PROCESSING" | "RECONCILED" | "FAILED";
export type SourceFileStatus = "UPLOADED" | "ANALYZING" | "MAPPING_REQUIRED" | "READY" | "FAILED";

export interface ApiFinancialInvestigation {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  period_start: string | null;
  period_end: string | null;
  base_currency: string;
  status: FinancialInvestigationStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  source_file_count: number;
}

export interface ApiSourceFile {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  row_count: number;
  column_count: number;
  status: SourceFileStatus;
  detected_source_type: string | null;
  detection_confidence: number | null;
  created_at: string;
}

export interface DemoDataRequest {
  orders: number;
  seed: number;
  anomaly_rate: number;
  scenario_types?: string[];
}

export interface ApiDemoDataResponse {
  financial_investigation_id: string;
  orders: number;
  seed: number;
  anomaly_rate: number;
  scenario_types: string[];
  sources: ApiSourceFile[];
}

export type SourceType = "SALES" | "ORDERS" | "PAYMENTS" | "SETTLEMENTS" | "REFUNDS" | "INVOICES" | "INVENTORY_MOVEMENTS" | "EMPLOYEE_ACTIONS" | "UNKNOWN";
export type MappingStatus = "PROPOSED" | "EDITED" | "CONFIRMED";

export interface ApiSourceAnalysis {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  source_file_id: string;
  headers: string[];
  sample_rows: Record<string, string | null>[];
  columns: { name: string; inferred_type: string; non_empty_count: number; unique_count: number; sample_values: string[]; min_value: string | null; max_value: string | null }[];
  source_type: SourceType;
  classification_confidence: number;
  reasoning_summary: string;
  provider_status: "OFFLINE_DETERMINISTIC" | "AI_PROVIDER" | "AI_PROVIDER_UNAVAILABLE";
  analyzed_at: string;
}

export interface ApiSourceMapping {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  source_file_id: string;
  source_column: string;
  canonical_field: string | null;
  confidence: number;
  required: boolean;
  inferred_type: string;
  ignored: boolean;
  status: MappingStatus;
  updated_at: string;
}

export interface ApiRelationshipProposal {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  source_file_id: string;
  target_source_file_id: string;
  join_fields: string[];
  evidence_summary: string;
  confidence: number;
  status: "PROPOSED" | "ACCEPTED" | "REJECTED" | "EDITED";
  updated_at: string;
}

export interface ApiDatasetVersion {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  version_no: number;
  status: "READY" | "FAILED";
  record_count: number;
  source_count: number;
  created_at: string;
}

export interface ApiReconciliationRun {
  id: string;
  organization_id: string;
  financial_investigation_id: string;
  dataset_version_id: string;
  status: "COMPLETED" | "FAILED";
  lifecycle_count: number;
  reconciled_count: number;
  exception_count: number;
  ambiguous_count: number;
  open_exposure_minor: number;
  started_at: string;
  completed_at: string | null;
}

export interface ApiReconciliationResult {
  id: string;
  run_id: string;
  order_id: string;
  status: string;
  exception_type: string | null;
  severity: string;
  exposure_minor: number;
  findings: { code: string; message: string; exposure_minor: number }[];
}

export interface ApiFinancialInvestigationPattern {
  pattern_id: string;
  financial_investigation_id: string;
  exception_type: string;
  occurrence_count: number;
  associated_exposure_minor: number;
  member_order_ids: string[];
  advisory: boolean;
  observation: string;
}
