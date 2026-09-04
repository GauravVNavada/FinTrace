import { expect, test } from "@playwright/test";

const investigation = {
  id: "FIN-DEMO-001",
  organization_id: "ORG-001",
  name: "FinTrace Flagship Demo",
  description: "Prepared synthetic lifecycle review",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  base_currency: "INR",
  status: "RECONCILED",
  created_by: "judge-controller",
  created_at: "2026-08-31T09:00:00Z",
  updated_at: "2026-08-31T09:05:00Z",
  source_file_count: 7,
};

const run = {
  id: "RR-DEMO-001",
  organization_id: "ORG-001",
  financial_investigation_id: investigation.id,
  dataset_version_id: "DS-DEMO-001",
  status: "COMPLETED",
  records_expected: 303,
  records_loaded: 303,
  records_consumed: 303,
  orphan_record_count: 0,
  rejected_record_count: 0,
  failure_reason: null,
  lifecycle_count: 50,
  reconciled_count: 39,
  exception_count: 7,
  ambiguous_count: 1,
  open_exposure_minor: 1874000,
  started_at: "2026-08-31T09:01:00Z",
  completed_at: "2026-08-31T09:05:00Z",
};

const exception = {
  id: "RRES-DEMO-001",
  run_id: run.id,
  order_id: "ORD-10005",
  status: "AMBIGUOUS",
  exception_type: "AMBIGUOUS_ASSOCIATION",
  severity: "HIGH",
  exposure_minor: 1874000,
  exposure_category: "CONTROL_RISK",
  findings: [{ code: "AMBIGUOUS_ASSOCIATION", message: "Two payment candidates remain plausible", exposure_minor: 1874000, exposure_category: "CONTROL_RISK" }],
};

const lifecycle = {
  organization_id: "ORG-001",
  order: { order_id: "ORD-10005", amount_minor: 1874000, status: "COMPLETED", created_at: "2026-08-01T09:00:00Z" },
  payments: [
    { payment_id: "PAY-20005-A", order_id: "ORD-10005", amount_minor: 1874000, status: "CAPTURED", captured_at: "2026-08-01T09:02:00Z", gateway_reference: "GTW-500005-A" },
    { payment_id: "PAY-20005-B", order_id: "ORD-10005", amount_minor: 1874000, status: "CAPTURED", captured_at: "2026-08-01T09:03:00Z", gateway_reference: "GTW-500005-B" },
  ],
  settlements: [],
  invoices: [{ invoice_id: "INV-40005", order_id: "ORD-10005", gross_minor: 1874000, status: "ACTIVE", created_at: "2026-08-01T09:04:00Z" }],
  refunds: [],
  inventory_movements: [{ movement_id: "MOV-50005", order_id: "ORD-10005", movement_type: "SALE", quantity: 1, occurred_at: "2026-08-01T09:05:00Z" }],
  employee_actions: [],
};

const aiResult = {
  investigation_id: "INV-DEMO-001",
  exception_id: exception.id,
  status: "UNRESOLVED",
  root_cause_code: null,
  summary: "Two candidate payments satisfy the available evidence; additional transaction reference or settlement evidence is required to resolve the ambiguous association.",
  supporting_evidence: [],
  contradictory_evidence: [],
  missing_evidence: ["Transaction reference", "Settlement record"],
  recommended_action_code: "REQUEST_PAYMENT_REVIEW",
  requires_human_review: true,
  evidence_score: 70,
  tool_calls: [
    { name: "get_payments_for_order", target: "ORD-10005", status: "SUCCEEDED", duration_ms: 12, sequence_no: 1, arguments: {}, result_record_ids: ["PAY-20005-A", "PAY-20005-B"], result_summary: "2 payment candidates returned · CAPTURED · INR 18,740 each" },
    { name: "get_settlements_for_payment", target: "ORD-10005", status: "SUCCEEDED", duration_ms: 10, sequence_no: 2, arguments: {}, result_record_ids: [], result_summary: "Settlement reference cannot disambiguate the two candidates" },
  ],
  created_at: "2026-08-31T09:06:00Z",
  provider: "stub",
  model: "test-fixture",
  prompt_version: "p0-iterative-v1",
  started_at: "2026-08-31T09:06:00Z",
  completed_at: "2026-08-31T09:06:01Z",
  latency_ms: 1000,
  verifier_passed: true,
  verifier_issues: [],
  rejected_evidence: [],
};

const auditEvent = {
  event_id: "AUD-DEMO-001",
  organization_id: "ORG-001",
  action: "RESOLUTION_REQUESTED",
  resource_id: exception.id,
  actor_id: "judge-controller",
  correlation_id: "e2e-demo",
  created_at: "2026-08-31T09:07:00Z",
};

test("Controller can complete the flagship investigation golden path", async ({ page }) => {
  let launched = false;
  let reviewRequested = false;

  await page.route("http://127.0.0.1:8001/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = async (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (path.endsWith("/ready")) return json({ status: "ready", storage_backend: "postgres" });
    if (path.endsWith("/auth/demo-login")) return json({ access_token: "e2e-controller-token", token_type: "bearer", expires_in: 3600, organization_id: "ORG-001", actor_id: "judge-controller", role: "CONTROLLER", display_name: "Judge Controller" });
    if (path.endsWith("/financial-investigations") && request.method() === "GET") return json(launched ? [investigation] : []);
    if (path.endsWith("/financial-investigations/flagship-demo")) { launched = true; return json(investigation); }
    if (path.endsWith(`/financial-investigations/${investigation.id}`)) return json(investigation);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/latest`)) return json(run);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results`)) return json([exception]);
    if (path.endsWith(`/financial-investigations/${investigation.id}/patterns`)) return json([]);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/investigation`) && request.method() === "GET") return json({}, 404);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/investigate`)) return json(aiResult);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/resolution-request`)) { reviewRequested = true; return json({ request_id: "REQ-DEMO-001", exception_id: exception.id, action_code: "REQUEST_PAYMENT_REVIEW", status: "PENDING_APPROVAL", financial_exposure: 18740, currency: "INR", required_capability: "CONTROLLER", required_approvals: 1, approvals_received: 0, requester_id: "judge-controller", created_at: "2026-08-31T09:07:00Z" }); }
    if (path.endsWith(`/lifecycles/${exception.order_id}`)) return json(lifecycle);
    if (path.endsWith("/ai/provider-health")) return json({ status: "CONNECTED", provider: "stub", model: "test-fixture", configured: true, latency_ms: 0, error_category: null, retryable: null, detail: "TEST FIXTURE / NON-LIVE", overall_status: "AVAILABLE", active_provider: "stub", providers: [] });
    if (path.endsWith("/audit-events")) return json(reviewRequested ? [auditEvent] : []);
    return json({}, 404);
  });

  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: "Close the period with confidence." })).toBeVisible();
  await page.getByRole("button", { name: "Continue to FinTrace" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("button", { name: "Launch Flagship Demo" }).last().click();
  await expect(page).toHaveURL(/investigation=FIN-DEMO-001/);
  await page.getByRole("link", { name: "Continue close" }).click();
  await expect(page.locator("h1", { hasText: "FinTrace Flagship Demo" })).toBeVisible();
  await page.getByRole("link", { name: "Reconciliation" }).click();
  await page.getByRole("button", { name: /ORD-10005/ }).click();
  await expect(page.getByText("What happened")).toBeVisible();
  await page.getByRole("button", { name: "Investigate evidence" }).click();
  await expect(page.getByText("Evidence assessment")).toBeVisible();
  await expect(page.getByText("AI investigation trace")).toBeVisible();
  await page.getByRole("button", { name: "Request controller decision" }).click();
  await expect(page.getByText(/Approval request · Pending Approval/)).toBeVisible();
  await page.getByRole("link", { name: "Audit", exact: true }).click();
  await expect(page.getByText("RESOLUTION_REQUESTED")).toBeVisible();
});
