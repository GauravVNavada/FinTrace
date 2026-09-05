import type { ApiAuditEvent, ApiDashboardSummary, ApiDatasetVersion, ApiDemoDataResponse, ApiEvaluation, ApiExceptionSummary, ApiFinancialInvestigation, ApiFinancialInvestigationPattern, ApiLifecycleGraph, ApiLifecycleResponse, ApiNormalizedRecord, ApiPattern, ApiReconciliationResult, ApiReconciliationRun, ApiRelationshipProposal, ApiResolutionRequest, ApiSourceAnalysis, ApiSourceFile, ApiSourceMapping, DemoDataRequest, EvaluationRunRequest, ResolutionActionCode, SourceType } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";
const organizationId = process.env.NEXT_PUBLIC_ORGANIZATION_ID ?? "ORG-001";
const configuredActorId = process.env.NEXT_PUBLIC_ACTOR_ID ?? "web-reviewer";
const configuredActorRole = process.env.NEXT_PUBLIC_ACTOR_ROLE ?? "ANALYST";

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code = "API_ERROR",
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

type ApiErrorPayload = { detail?: { code?: string; message?: string } | string; summary?: string };

const baseHeaders = {
  "X-Organization-Id": organizationId,
};

function handleExpiredSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("fintrace.access_token");
  window.localStorage.removeItem("fintrace.identity");
  window.location.replace("/login");
}

export type ClientIdentity = { actor_id: string; role: string; display_name: string; organization_id: string };

export function getDefaultClientIdentity(): ClientIdentity {
  return { actor_id: configuredActorId, role: configuredActorRole, display_name: "Development user", organization_id: organizationId };
}

export function getClientIdentity(): ClientIdentity {
  if (typeof window !== "undefined") {
    try {
      const stored = window.localStorage.getItem("fintrace.identity");
      if (stored) return JSON.parse(stored) as ClientIdentity;
    } catch { /* fall through to the explicit development defaults */ }
  }
  return getDefaultClientIdentity();
}

function runtimeIdentity() {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("fintrace.access_token") : null;
  if (token) return { Authorization: `Bearer ${token}` };
  return {
    "X-Actor-Id": configuredActorId,
    "X-Actor-Role": configuredActorRole,
  };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(baseHeaders);
  Object.entries(runtimeIdentity()).forEach(([key, value]) => headers.set(key, value));
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiClientError(0, "The FinTrace API could not be reached. Check that the API is running and try again.", "NETWORK_ERROR");
  }
  if (response.status === 401 && typeof window !== "undefined" && window.localStorage.getItem("fintrace.access_token")) {
    handleExpiredSession();
  }
  if (!response.ok) {
    const fallback = `API request failed with status ${response.status}`;
    let message = fallback;
    let code = "API_ERROR";
    try {
      const payload = await response.json() as ApiErrorPayload;
      const detail = payload.detail;
      if (typeof detail === "string") message = detail;
      if (detail && typeof detail === "object") {
        message = detail.message ?? payload.summary ?? fallback;
        code = detail.code ?? code;
      } else {
        message = payload.summary ?? message;
      }
    } catch { /* Keep the HTTP status message when the response is not JSON. */ }
    throw new ApiClientError(response.status, message, code, response.headers.get("X-Request-Id") ?? undefined);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

async function post<T>(path: string, body: unknown, idempotencyKey: string): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
  });
}

async function postForm<T>(path: string, body: FormData, idempotencyKey: string): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body });
}

async function patchJson<T>(path: string, body: unknown, idempotencyKey?: string): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}) },
    body: JSON.stringify(body),
  });
}

export function fetchDashboardSummary() {
  return get<ApiDashboardSummary>("/api/v1/dashboard/summary");
}

export function fetchReadiness() {
  return get<{ status: string; storage_backend: string }>("/ready");
}

export function demoLogin(role: "ANALYST" | "FINANCE_MANAGER" | "CONTROLLER") {
  return post<{ access_token: string; token_type: string; expires_in: number; organization_id: string; actor_id: string; role: string; display_name: string }>("/api/v1/auth/demo-login", { role }, requestId());
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

export function fetchUploadedLifecycle(investigationId: string, runId: string, resultId: string) {
  return get<ApiLifecycleResponse>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(resultId)}/lifecycle`);
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

export function fetchAuditEvents(resourceId?: string, limit = 200) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (resourceId) query.set("resource_id", resourceId);
  return get<ApiAuditEvent[]>(`/api/v1/audit-events?${query.toString()}`);
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

export function launchFlagshipDemo(idempotencyKey: string) {
  return post<ApiFinancialInvestigation>("/api/v1/financial-investigations/flagship-demo", {}, idempotencyKey);
}

export async function deleteSourceFile(investigationId: string, sourceFileId: string, idempotencyKey = requestId()) {
  await request<void>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}`, {
    method: "DELETE",
    headers: { "Idempotency-Key": idempotencyKey },
  });
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
  return patchJson<ApiSourceMapping>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/mappings/${encodeURIComponent(mappingId)}`, body, requestId());
}

export function confirmSourceMappings(investigationId: string, sourceFileId: string) {
  return post<{ status: "CONFIRMED"; confirmed_mapping_count: number; ignored_column_count: number }>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/mappings/confirm`, {}, requestId());
}

export function updateSourceClassification(investigationId: string, sourceFileId: string, source_type: SourceType) {
  return patchJson<ApiSourceAnalysis>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/sources/${encodeURIComponent(sourceFileId)}/classification`, { source_type }, requestId());
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

export function fetchNormalizedRecords(investigationId: string, datasetVersionId: string, limit = 10000) {
  return get<ApiNormalizedRecord[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/dataset-versions/${encodeURIComponent(datasetVersionId)}/records?limit=${limit}`);
}

export function runInvestigationReconciliation(investigationId: string, datasetVersionId?: string) {
  return post<ApiReconciliationRun>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs`, { dataset_version_id: datasetVersionId }, requestId());
}

export function fetchLatestReconciliation(investigationId: string) {
  return get<ApiReconciliationRun>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/latest`);
}

export function fetchReconciliationResults(investigationId: string, runId: string) {
  return get<ApiReconciliationResult[]>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results?limit=10000`);
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

export function requestFinancialResolution(investigationId: string, runId: string, resultId: string, actionCode: ResolutionActionCode, idempotencyKey = requestId()) {
  return post<ApiResolutionRequest>(`/api/v1/financial-investigations/${encodeURIComponent(investigationId)}/reconciliation-runs/${encodeURIComponent(runId)}/results/${encodeURIComponent(resultId)}/resolution-request`, { action_code: actionCode }, idempotencyKey);
}

function requestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getApiErrorMessage(error: unknown, fallback = "Something went wrong. Try again.") {
  if (error instanceof ApiClientError) return error.message;
  return fallback;
}
