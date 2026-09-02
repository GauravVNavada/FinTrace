import type { ApiAuditEvent, ApiDashboardSummary, ApiDatasetVersion, ApiDemoDataResponse, ApiEvaluation, ApiExceptionSummary, ApiFinancialInvestigation, ApiFinancialInvestigationPattern, ApiLifecycleGraph, ApiLifecycleResponse, ApiPattern, ApiReconciliationResult, ApiReconciliationRun, ApiRelationshipProposal, ApiResolutionRequest, ApiSourceAnalysis, ApiSourceFile, ApiSourceMapping, DemoDataRequest, EvaluationRunRequest, ResolutionActionCode, SourceType } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";
const organizationId = process.env.NEXT_PUBLIC_ORGANIZATION_ID ?? "ORG-001";
const actorId = process.env.NEXT_PUBLIC_ACTOR_ID ?? "web-reviewer";
const actorRole = process.env.NEXT_PUBLIC_ACTOR_ROLE ?? "ANALYST";

export class ApiClientError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      "X-Organization-Id": organizationId,
      "X-Actor-Id": actorId,
      "X-Actor-Role": actorRole
    },
    cache: "no-store"
  });
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const detail = await response.json() as { detail?: { message?: string } | string; summary?: string };
      message = typeof detail.detail === "string" ? detail.detail : detail.detail?.message ?? detail.summary ?? message;
    } catch { /* Keep the status message when the response is not JSON. */ }
    throw new ApiClientError(response.status, message);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown, idempotencyKey: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      "X-Organization-Id": organizationId,
      "X-Actor-Id": actorId,
      "X-Actor-Role": actorRole
    },
    body: JSON.stringify(body),
    cache: "no-store"
  });
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const detail = await response.json() as { detail?: { message?: string } | string; summary?: string };
      message = typeof detail.detail === "string" ? detail.detail : detail.detail?.message ?? detail.summary ?? message;
    } catch { /* Keep the status message when the response is not JSON. */ }
    throw new ApiClientError(response.status, message);
  }
  return response.json() as Promise<T>;
}

async function postForm<T>(path: string, body: FormData, idempotencyKey: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: {
      "Idempotency-Key": idempotencyKey,
      "X-Organization-Id": organizationId,
      "X-Actor-Id": actorId,
      "X-Actor-Role": actorRole
    },
    body,
    cache: "no-store"
  });
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const detail = await response.json() as { detail?: { message?: string } };
      message = detail.detail?.message ?? message;
    } catch { /* Keep the status message when the response is not JSON. */ }
    throw new ApiClientError(response.status, message);
  }
  return response.json() as Promise<T>;
}

async function patchJson<T>(path: string, body: unknown, idempotencyKey?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", "X-Organization-Id": organizationId, "X-Actor-Id": actorId, "X-Actor-Role": actorRole };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const response = await fetch(`${apiBaseUrl}${path}`, { method: "PATCH", headers, body: JSON.stringify(body), cache: "no-store" });
  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const detail = await response.json() as { detail?: { message?: string } | string };
      message = typeof detail.detail === "string" ? detail.detail : detail.detail?.message ?? message;
    } catch { /* Keep the status message when the response is not JSON. */ }
    throw new ApiClientError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export function fetchDashboardSummary() {
  return get<ApiDashboardSummary>("/api/v1/dashboard/summary");
}

export function fetchReadiness() {
  return get<{ status: string; storage_backend: string }>("/ready");
}

export function fetchProviderHealth() {
  return get<import("./types").ApiProviderHealth>("/api/v1/ai/provider-health");
}

export function fetchExceptions() {
  return get<ApiExceptionSummary[]>("/api/v1/exceptions");
}

export function fetchException(exceptionId: string) {
  return get<ApiExceptionSummary>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}`);
}

export function fetchLifecycle(orderId: string) {
  return get<ApiLifecycleResponse>(`/api/v1/lifecycles/${encodeURIComponent(orderId)}`);
}

export function fetchExceptionGraph(exceptionId: string) {
  return get<ApiLifecycleGraph>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/graph`);
}

export function startInvestigation(exceptionId: string, idempotencyKey: string) {
  return post<import("./types").ApiInvestigation>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/investigations`, {}, idempotencyKey);
}

export function requestResolution(exceptionId: string, actionCode: ResolutionActionCode, idempotencyKey: string) {
  return post<ApiResolutionRequest>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/resolution-request`, { action_code: actionCode }, idempotencyKey);
}

export function approveResolution(requestId: string, idempotencyKey: string) {
  return post<import("./types").ApiApprovalResponse>(`/api/v1/approvals/${encodeURIComponent(requestId)}/approve`, {}, idempotencyKey);
}

export function rejectResolution(requestId: string, idempotencyKey: string) {
  return post<import("./types").ApiApprovalResponse>(`/api/v1/approvals/${encodeURIComponent(requestId)}/reject`, {}, idempotencyKey);
}

export function fetchPatterns(limit = 20) {
  return get<ApiPattern[]>(`/api/v1/patterns?limit=${limit}`);
}

export function fetchLatestEvaluation() {
  return get<ApiEvaluation>("/api/v1/evaluation/latest");
}

export function fetchLatestAIEvaluation() {
  return get<import("./types").ApiAIEvaluation>("/api/v1/evaluation/ai/latest");
}

export function runAIEvaluation(idempotencyKey: string) {
  return post<import("./types").ApiAIEvaluation>("/api/v1/evaluation/ai/run", {}, idempotencyKey);
}

export function runEvaluation(request: EvaluationRunRequest, idempotencyKey: string) {
  return post<ApiEvaluation>("/api/v1/evaluation/run", request, idempotencyKey);
}

export function fetchAuditEvents(resourceId?: string) {
  const query = resourceId ? `?resource_id=${encodeURIComponent(resourceId)}` : "";
  return get<ApiAuditEvent[]>(`/api/v1/audit-events${query}`);
}

export function createFinancialInvestigation(payload: { name: string; description?: string; period_start?: string; period_end?: string; base_currency: string }, idempotencyKey: string) {
  return post<ApiFinancialInvestigation>("/api/v1/financial-investigations", payload, idempotencyKey);
}

export function fetchFinancialInvestigations() {
  return get<ApiFinancialInvestigation[]>("/api/v1/financial-investigations");
}

export function fetchFinancialInvestigation(investigationId: string) {
  return get<ApiFinancialInvestigation>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}`);
}

export function fetchSourceFiles(investigationId: string) {
  return get<ApiSourceFile[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources`);
}

export function uploadSourceFile(investigationId: string, file: File, idempotencyKey: string) {
  const form = new FormData();
  form.append("file", file);
  return postForm<ApiSourceFile>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources`, form, idempotencyKey);
}

export function generateDemoData(investigationId: string, payload: DemoDataRequest, idempotencyKey: string) {
  return post<ApiDemoDataResponse>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/demo-data`, payload, idempotencyKey);
}

export async function deleteSourceFile(investigationId: string, sourceFileId: string) {
  const response = await fetch(`${apiBaseUrl}/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}`, {
    method: "DELETE",
    headers: { "X-Organization-Id": organizationId, "X-Actor-Id": actorId, "X-Actor-Role": actorRole },
    cache: "no-store"
  });
  if (!response.ok) throw new ApiClientError(response.status, `API request failed with status ${response.status}`);
}

export function analyzeSourceFile(investigationId: string, sourceFileId: string) {
  return post<ApiSourceAnalysis>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/analyze`, {}, requestId());
}

export function fetchSourceAnalysis(investigationId: string, sourceFileId: string) {
  return get<ApiSourceAnalysis>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/analysis`);
}

export function fetchSourceMappings(investigationId: string, sourceFileId: string) {
  return get<ApiSourceMapping[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/mappings`);
}

export function editSourceMapping(investigationId: string, sourceFileId: string, mappingId: string, body: { canonical_field: string | null; ignored: boolean }) {
  return patchJson<ApiSourceMapping>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/mappings/${encodeURIComponent(mappingId)}`, body);
}

export function confirmSourceMappings(investigationId: string, sourceFileId: string) {
  return post<{ status: "CONFIRMED"; confirmed_mapping_count: number; ignored_column_count: number }>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/mappings/confirm`, {}, requestId());
}

export function updateSourceClassification(investigationId: string, sourceFileId: string, source_type: SourceType) {
  return patchJson<ApiSourceAnalysis>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/classification`, { source_type });
}

export function discoverRelationships(investigationId: string) {
  return post<ApiRelationshipProposal[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/relationships/discover`, {}, requestId());
}

export function fetchRelationships(investigationId: string) {
  return get<ApiRelationshipProposal[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/relationships`);
}

export function decideRelationship(investigationId: string, relationshipId: string, status: "ACCEPTED" | "REJECTED") {
  return patchJson<ApiRelationshipProposal>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/relationships/${encodeURIComponent(relationshipId)}`, { status }, requestId());
}

export function normalizeDataset(investigationId: string) {
  return post<ApiDatasetVersion>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/dataset-versions/normalize`, {}, requestId());
}

export function fetchLatestDataset(investigationId: string) {
  return get<ApiDatasetVersion>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/dataset-versions/latest`);
}

export function runInvestigationReconciliation(investigationId: string, datasetVersionId?: string) {
  return post<ApiReconciliationRun>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs`, { dataset_version_id: datasetVersionId }, requestId());
}

export function fetchLatestReconciliation(investigationId: string) {
  return get<ApiReconciliationRun>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/latest`);
}

export function fetchReconciliationResults(investigationId: string, runId: string) {
  return get<ApiReconciliationResult[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results`);
}

export function fetchFinancialInvestigationPatterns(investigationId: string) {
  return get<ApiFinancialInvestigationPattern[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/patterns`);
}

export function investigateReconciliationResult(investigationId: string, runId: string, resultId: string) {
  return post<import("./types").ApiInvestigation>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(resultId)}/investigate`, {}, requestId());
}

export function fetchReconciliationInvestigation(investigationId: string, runId: string, resultId: string) {
  return get<import("./types").ApiInvestigation>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(resultId)}/investigation`);
}

export function requestFinancialResolution(investigationId: string, runId: string, resultId: string, actionCode: ResolutionActionCode, idempotencyKey: string) {
  return post<ApiResolutionRequest>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(resultId)}/resolution-request`, { action_code: actionCode }, idempotencyKey);
}

function requestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
