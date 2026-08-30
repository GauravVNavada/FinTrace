import type { ApiAuditEvent, ApiDashboardSummary, ApiEvaluation, ApiExceptionSummary, ApiPattern } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const organizationId = process.env.NEXT_PUBLIC_ORGANIZATION_ID ?? "ORG-001";
const actorId = process.env.NEXT_PUBLIC_ACTOR_ID ?? "web-reviewer";
const actorRole = process.env.NEXT_PUBLIC_ACTOR_ROLE ?? "CONTROLLER";

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
    throw new ApiClientError(response.status, `API request failed with status ${response.status}`);
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
    throw new ApiClientError(response.status, `API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchDashboardSummary() {
  return get<ApiDashboardSummary>("/api/v1/dashboard/summary");
}

export function fetchExceptions() {
  return get<ApiExceptionSummary[]>("/api/v1/exceptions");
}

export function fetchException(exceptionId: string) {
  return get<ApiExceptionSummary>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}`);
}

export function fetchLifecycle(orderId: string) {
  return get(`/api/v1/lifecycles/${encodeURIComponent(orderId)}`);
}

export function startInvestigation(exceptionId: string, idempotencyKey: string) {
  return post<import("./types").ApiInvestigation>(`/api/v1/exceptions/${encodeURIComponent(exceptionId)}/investigations`, {}, idempotencyKey);
}

export function fetchPatterns(limit = 20) {
  return get<ApiPattern[]>(`/api/v1/patterns?limit=${limit}`);
}

export function fetchLatestEvaluation() {
  return get<ApiEvaluation>("/api/v1/evaluation/latest");
}

export function fetchAuditEvents() {
  return get<ApiAuditEvent[]>("/api/v1/audit-events");
}
