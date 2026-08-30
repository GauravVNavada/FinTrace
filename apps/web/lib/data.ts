import type { ExceptionDetail, ExceptionItem, Investigation, Metric, Pattern } from "./types";

export const appConfig = {
  productName: "FinTrace",
  workspaceName: "Northstar Retail Group",
  workspaceEnvironment: "Production workspace",
  batchName: "August close · Run 024",
  lastSynced: "30 Aug 2026, 14:32 IST",
  currency: "INR" as const,
  unresolvedExceptions: 56,
  actor: { name: "Aarav Mehta", firstName: "Aarav", initials: "AM", role: "Finance analyst" }
};

export const metrics: Metric[] = [
  { label: "Lifecycle records", value: "1,000", detail: "100% of batch processed", trend: "+8.4%", tone: "neutral" },
  { label: "Auto-reconciled", value: "86.7%", detail: "867 of 1,000 lifecycles", trend: "+2.1%", tone: "positive" },
  { label: "Open exposure", value: "₹4,82,390", detail: "Across 133 exceptions", trend: "−6.8%", tone: "warning" },
  { label: "Requires review", value: "17", detail: "12.8% of exceptions", trend: "−4 cases", tone: "critical" }
];

export const healthBreakdown = [
  { label: "Reconciled", value: 867, percent: 86.7, tone: "success" },
  { label: "With variance", value: 60, percent: 6, tone: "warning" },
  { label: "Open exception", value: 56, percent: 5.6, tone: "destructive" },
  { label: "Ambiguous", value: 17, percent: 1.7, tone: "muted" }
];

export const exceptionItems: ExceptionItem[] = [
  {
    id: "EXC-1042", orderId: "ORD-2041", type: "REFUND_WITHOUT_INVENTORY_RETURN", label: "Refund without inventory return", severity: "HIGH", status: "OPEN", exposure: 18740, currency: "INR", detectedAt: "12 min ago", summary: "Full refund completed, but neither ERP reversal nor inventory return is present.", source: "Refunds · Inventory", ruleCount: 4, assignee: "Unassigned", pattern: "Manual POS refund"
  },
  {
    id: "EXC-1037", orderId: "ORD-1978", type: "DUPLICATE_PAYMENT", label: "Duplicate payment capture", severity: "HIGH", status: "IN_REVIEW", exposure: 12990, currency: "INR", detectedAt: "28 min ago", summary: "Two captured gateway payments share the same order reference.", source: "Payments", ruleCount: 3, assignee: "A. Mehta"
  },
  {
    id: "EXC-1031", orderId: "ORD-1988", type: "ERP_AMOUNT_MISMATCH", label: "Invoice amount mismatch", severity: "MEDIUM", status: "OPEN", exposure: 4500, currency: "INR", detectedAt: "44 min ago", summary: "Invoice total exceeds captured amount by ₹4,500.", source: "Payments · ERP", ruleCount: 2, assignee: "Unassigned"
  },
  {
    id: "EXC-1024", orderId: "ORD-1902", type: "MISSING_SETTLEMENT", label: "Settlement not received", severity: "MEDIUM", status: "OPEN", exposure: 8340, currency: "INR", detectedAt: "1 hr ago", summary: "Captured payment has no settlement after the configured T+2 window.", source: "Payments · Settlements", ruleCount: 2, assignee: "Unassigned"
  },
  {
    id: "EXC-1016", orderId: "ORD-1844", type: "SETTLEMENT_TIMING", label: "Settlement timing difference", severity: "LOW", status: "RESOLVED", exposure: 0, currency: "INR", detectedAt: "2 hrs ago", summary: "Valid settlement arrived outside the primary matching window.", source: "Settlements", ruleCount: 1, assignee: "S. Iyer"
  },
  {
    id: "EXC-1009", orderId: "ORD-1771", type: "ERP_INVOICE_MISSING", label: "Invoice not created", severity: "HIGH", status: "ESCALATED", exposure: 22400, currency: "INR", detectedAt: "3 hrs ago", summary: "Order and payment are complete, but no ERP invoice was found.", source: "Orders · ERP", ruleCount: 3, assignee: "N. Rao"
  }
];

const flagshipInvestigation: Investigation = {
  status: "SUPPORTED",
  rootCause: "Incomplete refund workflow",
  rootCauseCode: "INCOMPLETE_REFUND_WORKFLOW",
  summary: "The customer refund completed successfully, but downstream operational reversals did not complete. The available evidence supports a workflow handoff failure rather than a settlement issue.",
  evidenceScore: 91,
  supportingEvidence: [
    { source: "Refund", recordId: "RFND-2991", fact: "Full refund of ₹18,740 completed at 11:12:01.", tone: "positive" },
    { source: "ERP", fact: "No cancellation or reversal exists for invoice INV-4012.", tone: "warning" },
    { source: "Inventory", fact: "No RETURN movement exists for order ORD-2041.", tone: "warning" },
    { source: "Employee log", recordId: "ACT-7021", fact: "Manual POS refund approved by EMP-42.", tone: "neutral" }
  ],
  contradictoryEvidence: [],
  missingEvidence: ["Physical goods receipt confirmation", "Reason code for manual refund"],
  action: "Request inventory verification and ERP cancellation review",
  actionCode: "REQUEST_INVENTORY_VERIFICATION",
  requiresHumanReview: true,
  tools: [
    { name: "get_order", target: "ORD-2041", duration: "18ms" },
    { name: "get_payments_for_order", target: "ORD-2041", duration: "21ms" },
    { name: "get_refunds_for_payment", target: "PAY-8271", duration: "19ms" },
    { name: "get_invoice_for_order", target: "ORD-2041", duration: "16ms" },
    { name: "get_inventory_movements", target: "ORD-2041", duration: "23ms" },
    { name: "get_employee_action_logs", target: "ORD-2041", duration: "20ms" }
  ]
};

export const exceptionDetails: Record<string, ExceptionDetail> = {
  "EXC-1042": {
    ...exceptionItems[0],
    lifecycle: [
      { id: "ORD-2041", source: "POS order", status: "confirmed", amount: "₹18,740", detail: "Completed sale · BLR-03" },
      { id: "PAY-8271", source: "Payment gateway", status: "confirmed", amount: "₹18,740", detail: "Captured · UPI" },
      { id: "INV-4012", source: "ERP invoice", status: "confirmed", amount: "₹18,740", detail: "Active · No reversal" },
      { id: "RFND-2991", source: "Refund", status: "confirmed", amount: "₹18,740", detail: "Full refund processed" },
      { id: "—", source: "Inventory", status: "missing", detail: "Expected RETURN movement not observed" },
      { id: "—", source: "ERP reversal", status: "missing", detail: "Expected cancellation not observed" }
    ],
    timeline: [
      { time: "10:42:01", title: "Order created", detail: "ORD-2041 · ₹18,740", source: "POS", state: "complete" },
      { time: "10:42:17", title: "Payment captured", detail: "PAY-8271 · UPI", source: "Gateway", state: "complete" },
      { time: "10:43:02", title: "Invoice generated", detail: "INV-4012 · ₹18,740", source: "ERP", state: "complete" },
      { time: "11:11:44", title: "Refund approved", detail: "RFND-2991 · Manual POS workflow", source: "Employee log", state: "complete" },
      { time: "11:12:01", title: "Refund processed", detail: "₹18,740 returned to customer", source: "Gateway", state: "complete" },
      { time: "11:12:05", title: "Inventory return expected", detail: "No movement received within workflow SLA", source: "Inventory", state: "warning" },
      { time: "11:45:00", title: "Exception generated", detail: "REFUND_WITHOUT_INVENTORY_RETURN", source: "FinTrace rule engine", state: "missing" }
    ],
    investigation: flagshipInvestigation,
    policy: { owner: "Controller", reason: "High exposure + financial reversal", state: "Approval required" },
    audit: [
      { time: "12:00:00", actor: "FinTrace rules", action: "EXCEPTION_CREATED", detail: "4 rules triggered" },
      { time: "12:04:18", actor: "A. Mehta · Analyst", action: "INVESTIGATION_STARTED", detail: "Bounded evidence collection" },
      { time: "12:04:19", actor: "Financial investigator", action: "AI_TOOL_CALLED", detail: "6 read-only tools" },
      { time: "12:04:20", actor: "Deterministic verifier", action: "RESULT_VERIFIED", detail: "Evidence score 91/100" }
    ]
  }
};

export const patterns: Pattern[] = [
  { id: "PAT-18", title: "Manual POS refund handoff", description: "Refunds are being completed before the inventory and ERP reversal steps are confirmed.", incidents: 12, exposure: 71420, location: "BLR-03", control: "Require inventory disposition before refund workflow reaches COMPLETE.", severity: "HIGH" },
  { id: "PAT-12", title: "ERP invoice creation lag", description: "Orders from the evening batch regularly miss the first invoice sync window.", incidents: 8, exposure: 19340, location: "South region", control: "Retry ERP creation after 15 minutes and alert after T+1.", severity: "MEDIUM" },
  { id: "PAT-07", title: "Duplicate gateway callback", description: "A gateway callback retry is creating a second capture candidate for a small set of orders.", incidents: 5, exposure: 42800, location: "All stores", control: "Enforce gateway event idempotency on capture reference.", severity: "HIGH" }
];

export const recentRuns = [
  { name: "August close · Run 024", records: "1,000", match: "86.7%", exceptions: "133", completed: "Today, 14:32", status: "Completed" },
  { name: "August close · Run 023", records: "1,000", match: "84.6%", exceptions: "154", completed: "29 Aug, 14:28", status: "Completed" },
  { name: "August close · Run 022", records: "1,000", match: "83.9%", exceptions: "161", completed: "28 Aug, 14:31", status: "Completed" }
];

export function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}
