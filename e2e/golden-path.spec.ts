import { expect, test } from "@playwright/test";

const investigation = {
  id: "FIN-591BF1714F6A",
  organization_id: "ORG-001",
  name: "August 2026 Independent Close",
  description: "Prepared synthetic lifecycle review",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  base_currency: "INR",
  status: "RECONCILED",
  created_by: "reviewer-controller",
  created_at: "2026-08-31T09:00:00Z",
  updated_at: "2026-08-31T09:05:00Z",
  source_file_count: 7,
};

const run = {
  id: "RR-SAMPLE-001",
  organization_id: "ORG-001",
  financial_investigation_id: investigation.id,
  dataset_version_id: "DS-SAMPLE-001",
  status: "COMPLETED",
  records_expected: 544,
  records_loaded: 544,
  records_consumed: 544,
  orphan_record_count: 0,
  rejected_record_count: 0,
  failure_reason: null,
  lifecycle_count: 90,
  reconciled_count: 76,
  exception_count: 12,
  ambiguous_count: 2,
  open_exposure_minor: 5929300,
  started_at: "2026-08-31T09:01:00Z",
  completed_at: "2026-08-31T09:05:00Z",
};

const exception = {
  id: "RRES-SAMPLE-001",
  run_id: run.id,
  order_id: "ORD-10005",
  status: "AMBIGUOUS",
  exception_type: "AMBIGUOUS_ASSOCIATION",
  severity: "HIGH",
  exposure_minor: 1874000,
  exposure_category: "CONTROL_RISK",
  findings: [{ code: "AMBIGUOUS_ASSOCIATION", message: "Two payment candidates remain plausible", exposure_minor: 1874000, exposure_category: "CONTROL_RISK" }],
};

const secondAmbiguous = {
  id: "RRES-SAMPLE-003",
  run_id: run.id,
  order_id: "ORD-10088",
  status: "AMBIGUOUS",
  exception_type: "AMBIGUOUS_ASSOCIATION",
  severity: "HIGH",
  exposure_minor: 249900,
  exposure_category: "CONTROL_RISK",
  findings: [{ code: "AMBIGUOUS_ASSOCIATION", message: "Two payment candidates remain plausible", exposure_minor: 249900, exposure_category: "CONTROL_RISK" }],
};

const missingSettlement = {
  id: "RRES-SAMPLE-002",
  run_id: run.id,
  order_id: "ORD-10006",
  status: "EXCEPTION",
  exception_type: "MISSING_SETTLEMENT",
  severity: "HIGH",
  exposure_minor: 2719600,
  exposure_category: "CONTROL_RISK",
  findings: [{ code: "MISSING_SETTLEMENT", message: "Captured payment has no matching settlement", exposure_minor: 2719600, exposure_category: "CONTROL_RISK" }],
};

const sources = Array.from({ length: 7 }, (_, index) => ({
  id: `SRC-SAMPLE-${index + 1}`,
  organization_id: "ORG-001",
  financial_investigation_id: investigation.id,
  original_filename: ["August_Orders.xlsx", "Gateway_Payments.csv", "Bank_Settlement_Report.xlsx", "ERP_Invoice_Register.csv", "Refund_Report.xlsx", "Inventory_Movements.csv", "Employee_Actions.csv"][index],
  mime_type: "text/csv",
  size_bytes: 1200,
  row_count: [90, 94, 88, 90, 2, 90, 90][index],
  column_count: 8,
  status: "READY",
  detected_source_type: ["ORDERS", "PAYMENTS", "SETTLEMENTS", "INVOICES", "REFUNDS", "INVENTORY_MOVEMENTS", "EMPLOYEE_ACTIONS"][index],
  detection_confidence: 0.99,
  created_at: "2026-08-31T09:00:00Z",
}));

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

const missingLifecycle = {
  organization_id: "ORG-001",
  order: { order_id: "ORD-10006", amount_minor: 2719600, status: "COMPLETED", created_at: "2026-08-01T09:10:00Z" },
  payments: [{ payment_id: "PAY-20006", order_id: "ORD-10006", amount_minor: 2719600, status: "CAPTURED", captured_at: "2026-08-01T09:12:00Z" }],
  settlements: [], invoices: [{ invoice_id: "INV-40006", order_id: "ORD-10006", gross_minor: 2719600, status: "ACTIVE", created_at: "2026-08-01T09:13:00Z" }], refunds: [], inventory_movements: [{ movement_id: "MOV-50006", order_id: "ORD-10006", movement_type: "SALE", quantity: 1, occurred_at: "2026-08-01T09:14:00Z" }], employee_actions: [],
};

const aiResult = {
  investigation_id: "INV-SAMPLE-001",
  exception_id: exception.id,
  status: "UNRESOLVED",
  root_cause_code: null,
  summary: "Two candidate payments satisfy the available evidence; additional transaction reference or settlement evidence is required to resolve the ambiguous association.",
  supporting_evidence: lifecycle.payments.flatMap(payment => [
    { source: "payment", record_id: payment.payment_id, fact: "Payment status is CAPTURED.", field: "status", operator: "equals", expected_value: payment.status, verified: true },
    { source: "payment", record_id: payment.payment_id, fact: "Payment amount.", field: "amount_minor", operator: "equals", expected_value: payment.amount_minor, verified: true },
    { source: "payment", record_id: payment.payment_id, fact: "Capture time.", field: "captured_at", operator: "equals", expected_value: payment.captured_at, verified: true },
  ]),
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
  event_id: "AUD-SAMPLE-001",
  organization_id: "ORG-001",
  action: "RESOLUTION_REQUESTED",
  resource_id: exception.id,
  actor_id: "reviewer-controller",
  correlation_id: "e2e-sample",
  created_at: "2026-08-31T09:07:00Z",
};

for (const retryFailed of [false, true]) {
test(`Controller can complete the canonical close golden path (retry=${retryFailed})`, async ({ page }) => {
  let reviewRequested = false;

  await page.route("http://127.0.0.1:8001/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = async (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (path.endsWith("/ready")) return json({ status: "ready", storage_backend: "postgres" });
    if (path.endsWith("/dashboard/latest-run")) return json(run);
    if (path.endsWith("/auth/local-login")) return json({ access_token: "e2e-controller-token", token_type: "bearer", expires_in: 3600, organization_id: "ORG-001", actor_id: "reviewer-controller", role: "CONTROLLER", display_name: "Reviewer Controller" });
    if (path.endsWith("/financial-investigations") && request.method() === "GET") return json([{ ...investigation, id: "FIN-EMPTY", name: "New empty close", source_file_count: 0 }, investigation]);
    if (path.endsWith("/financial-investigations/flagship-sample")) return json(investigation);
    if (path.endsWith(`/financial-investigations/${investigation.id}`)) return json(investigation);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/latest`)) return json(run);
    if (path.endsWith(`/financial-investigations/${investigation.id}/sources`)) return json(sources);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results`)) return json([exception, secondAmbiguous, missingSettlement]);
    if (path.endsWith(`/financial-investigations/${investigation.id}/patterns`)) return json([]);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/investigation`) && request.method() === "GET") return retryFailed ? json({ ...aiResult, status: "FAILED", summary: "The AI response could not be validated.", supporting_evidence: [], verifier_passed: false }) : json({}, 404);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/investigate`)) return json(aiResult);
    if (path.endsWith(`/financial-investigations/${investigation.id}/reconciliation-runs/${run.id}/results/${exception.id}/resolution-request`)) { reviewRequested = true; return json({ request_id: "REQ-SAMPLE-001", exception_id: exception.id, action_code: "REQUEST_PAYMENT_REVIEW", status: "PENDING_APPROVAL", financial_exposure: 18740, currency: "INR", required_capability: "CONTROLLER", required_approvals: 1, approvals_received: 0, requester_id: "reviewer-controller", created_at: "2026-08-31T09:07:00Z" }); }
    if (path.endsWith(`/results/${missingSettlement.id}/lifecycle`)) return json(missingLifecycle);
    if (path.endsWith(`/results/${exception.id}/lifecycle`)) return json(lifecycle);
    if (path.endsWith("/ai/provider-health")) return json({ status: "CONNECTED", provider: "stub", model: "test-fixture", configured: true, latency_ms: 0, error_category: null, retryable: null, detail: "TEST FIXTURE / NON-LIVE", overall_status: "AVAILABLE", active_provider: "stub", providers: [] });
    if (path.endsWith("/audit-events")) return json(reviewRequested ? [auditEvent] : []);
    return json({}, 404);
  });

  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: "Close the period with clarity." })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-login.png", fullPage: true });
  await page.getByRole("button", { name: "Continue to FinTrace" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Financial Close Control" })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-home.png", fullPage: true });
  await page.goto("/investigations");
  await expect(page.getByRole("heading", { name: "Financial closes" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Start a new close" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open latest close" })).toBeVisible();
  await page.goto(`/investigations/${investigation.id}/data`);
  await expect(page.getByRole("heading", { name: investigation.name })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-data.png", fullPage: true });
  await page.goto(`/investigations/${investigation.id}/reconciliation`);
  await expect(page.getByText("What FinTrace found")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-results.png", fullPage: true });
  await page.getByRole("link", { name: /ORD-10005/ }).click();
  await expect(page.getByText("What happened")).toBeVisible();
  await page.getByRole("button", { name: retryFailed ? "Retry AI investigation" : "Investigate evidence" }).click();
  await expect(page.getByRole("heading", { name: "Assessment · needs evidence" })).toBeVisible();
  await expect(page.getByText("Cited fields passed verification. The cause remains unresolved.")).toBeVisible();
  await expect(page.getByText("Evidence confidence", { exact: true })).toBeVisible();
  await expect(page.getByText("Partial evidence", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Compare the payments" })).toBeVisible();
  await page.getByText("Evidence cited in this assessment · 2 records", { exact: true }).click();
  await expect(page.getByText("CAPTURED", { exact: true }).last()).toBeVisible();
  await expect(page.getByText("Automated test fixture · not live AI")).toBeVisible();
  await expect(page.getByRole("heading", { name: "What would resolve this" })).toBeVisible();
  await page.getByRole("button", { name: "Request transaction reference" }).click();
  await expect(page.getByRole("button", { name: "Reference requested" })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-ambiguous-case.png", fullPage: true });
  await page.goto(`/investigations/${investigation.id}/reconciliation?result=${missingSettlement.id}`);
  await expect(page.getByRole("heading", { name: "Missing settlement" })).toBeVisible();
  await expect(page.getByText("NEEDS DECISION", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Investigate evidence" })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-missing-settlement.png", fullPage: true });
  await page.goto(`/investigations/${investigation.id}/attention`);
  await expect(page.getByRole("heading", { name: "Human work queue" })).toBeVisible();
  await expect(page.getByText("NEEDS EVIDENCE").first()).toBeVisible();
  await expect(page.getByText("EXPLAINED", { exact: true })).toHaveCount(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/redesign-attention.png", fullPage: true });
  await page.getByRole("link", { name: "Audit", exact: true }).last().click();
  await expect(page.getByText("RESOLUTION_REQUESTED")).toBeVisible();
});
}
