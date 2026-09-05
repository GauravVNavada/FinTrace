"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, FileSpreadsheet, FileText, FolderSearch, Loader2, Plus, ShieldCheck, Sparkles, Trash2, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, FileInput, Input, Select, Textarea } from "@fintrace/ui";
import { analyzeSourceFile, ApiClientError, approveResolution, confirmSourceMappings, createFinancialInvestigation, decideRelationship, deleteSourceFile, discoverRelationships, editSourceMapping, fetchFinancialInvestigation, fetchFinancialInvestigationPatterns, fetchFinancialInvestigations, fetchLatestDataset, fetchLatestReconciliation, fetchProviderHealth, fetchReconciliationResults, fetchReconciliationInvestigation, fetchNormalizedRecords, fetchRelationships, fetchSourceAnalysis, fetchSourceFiles, fetchSourceMappings, fetchLifecycle, generateDemoData, getClientIdentity, investigateReconciliationResult, launchFlagshipDemo, normalizeDataset, rejectResolution, requestFinancialResolution, runInvestigationReconciliation, updateSourceClassification, uploadSourceFile } from "../lib/api-client";
import type { ApiFinancialInvestigation, ApiFinancialInvestigationPattern, ApiInvestigation, ApiLifecycleResponse, ApiNormalizedRecord, ApiProviderHealth, ApiReconciliationResult, ApiReconciliationRun, ApiRelationshipProposal, ApiResolutionRequest, ApiSourceAnalysis, ApiSourceFile, ApiSourceMapping, DemoDataRequest, ResolutionActionCode, SourceType } from "../lib/types";
import { PageHeading } from "./dashboard";

const allowedExtensions = [".csv", ".xlsx"];
const canonicalFieldsBySourceType: Record<SourceType, string[]> = {
  SALES: ["order_id", "store_code", "amount", "currency", "created_at"],
  ORDERS: ["order_id", "store_code", "amount", "currency", "status", "created_at"],
  PAYMENTS: ["payment_id", "order_id", "amount", "gateway_fee_amount", "currency", "status", "captured_at"],
  SETTLEMENTS: ["settlement_id", "payment_id", "gross_amount", "fee_amount", "tax_amount", "net_amount", "currency", "settled_at"],
  REFUNDS: ["refund_id", "payment_id", "amount", "currency", "status", "processed_at"],
  INVOICES: ["invoice_id", "order_id", "amount", "currency", "status", "created_at"],
  INVENTORY_MOVEMENTS: ["movement_id", "order_id", "sku", "quantity", "movement_type", "occurred_at", "unit_cost", "inventory_value"],
  EMPLOYEE_ACTIONS: ["action_id", "entity_type", "entity_id", "employee_id", "action", "occurred_at"],
  UNKNOWN: [],
};
function currentActor() {
  const identity = getClientIdentity();
  return { id: identity.actor_id, role: identity.role };
}

function displayStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, character => character.toUpperCase());
}

export function InvestigationStageNav({ investigationId }: { investigationId: string }) {
  const pathname = usePathname();
  const stages = [
    ["Overview", `/investigations/${investigationId}`],
    ["Data", `/investigations/${investigationId}/data`],
    ["Reconciliation", `/investigations/${investigationId}/reconciliation`],
    ["Attention", `/investigations/${investigationId}/attention`],
    ["Audit", `/audit?resource_id=${encodeURIComponent(investigationId)}`],
  ] as const;
  return <nav aria-label="Investigation stages" className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-border bg-card p-1">{stages.map(([label, href]) => { const active = label === "Overview" ? pathname === stages[0][1] : label === "Data" ? pathname.includes("/data") || pathname.includes("/sources") || pathname.includes("/relationships") : pathname === href.split("?")[0]; return <Link key={label} href={href} aria-current={active ? "page" : undefined} className={`whitespace-nowrap rounded-md px-3 py-2 text-[11px] font-semibold transition-colors ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{label}</Link>; })}</nav>;
}

type LifecycleStepState = "PRESENT" | "EXPECTED BUT MISSING" | "NOT APPLICABLE" | "MISMATCH" | "AMBIGUOUS";

function lifecycleStepState(label: string, record: Record<string, unknown> | undefined, exceptionType: string | null, lifecycle: ApiLifecycleResponse): LifecycleStepState {
  if (exceptionType === "AMBIGUOUS_ASSOCIATION" && label === "PAYMENT") return "AMBIGUOUS";
  if (label === "SETTLEMENT" && (exceptionType === "MISSING_SETTLEMENT" || exceptionType === "SETTLEMENT_MISSING") && !record) return "EXPECTED BUT MISSING";
  if (label === "INVENTORY" && exceptionType?.includes("INVENTORY")) {
    const returnMovement = lifecycle.inventory_movements.find(item => item.movement_type === "RETURN");
    if (!returnMovement && exceptionType === "REFUND_WITHOUT_INVENTORY_RETURN") return "EXPECTED BUT MISSING";
    if (exceptionType === "INVENTORY_VALUE_MISMATCH" || exceptionType === "INVENTORY_QUANTITY_MISMATCH" || exceptionType === "INVENTORY_RESTORED_WITHOUT_REFUND") return "MISMATCH";
  }
  if (label === "INVOICE" && exceptionType === "ERP_AMOUNT_MISMATCH" && record) return "MISMATCH";
  if (record) return "PRESENT";
  if (label === "ORDER" || label === "PAYMENT" || label === "SETTLEMENT" || label === "INVOICE") return "EXPECTED BUT MISSING";
  return "NOT APPLICABLE";
}

function lifecycleStateClasses(state: LifecycleStepState) {
  if (state === "EXPECTED BUT MISSING" || state === "MISMATCH") return "border-destructive/30 bg-destructive/5 text-destructive";
  if (state === "AMBIGUOUS") return "border-warning/40 bg-warning/10 text-warning";
  if (state === "NOT APPLICABLE") return "border-border bg-muted/30 text-muted-foreground";
  return "border-border bg-card text-success";
}

function LifecyclePreview({ lifecycle, exceptionType }: { lifecycle: ApiLifecycleResponse; exceptionType: string | null }) {
  const steps: Array<[string, Record<string, unknown> | undefined, string]> = [
    ["ORDER", lifecycle.order, "order_id"],
    ["PAYMENT", lifecycle.payments[0], "payment_id"],
    ["SETTLEMENT", lifecycle.settlements[0], "settlement_id"],
    ["INVOICE", lifecycle.invoices[0], "invoice_id"],
    ["REFUND", lifecycle.refunds[0], "refund_id"],
    ["INVENTORY", lifecycle.inventory_movements.find(item => item.movement_type === "RETURN") ?? lifecycle.inventory_movements[0], "movement_id"],
  ];
  const formatMinor = (value: unknown) => value === undefined || value === null || value === "" ? "Unavailable" : Number(value) / 100;
  return <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4"><div className="flex items-center justify-between gap-3"><div><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Financial lifecycle</div><p className="mt-1 text-[11px] text-muted-foreground">Only expected breaks are marked as problems. Optional steps are shown separately.</p></div><span className="text-[10px] text-muted-foreground">Order → payment → settlement → invoice → refund → inventory</span></div><div className="mt-3 grid gap-2 sm:grid-cols-6">{steps.map(([label, record, idKey], index) => { const state = lifecycleStepState(label, record, exceptionType, lifecycle); const id = record?.[idKey]; return <React.Fragment key={label}><div className={`rounded-md border p-2 ${lifecycleStateClasses(state)}`}><div className="flex items-center justify-between gap-1"><span className="text-[10px] font-bold text-foreground">{label}</span><span className="text-right text-[9px] font-semibold">{state}</span></div><div className="mt-2 truncate font-mono text-[9px] text-muted-foreground">{id ? String(id) : state === "NOT APPLICABLE" ? "No refund flow" : "Expected record not found"}</div></div>{index < steps.length - 1 && <div className="hidden items-center justify-center text-muted-foreground sm:flex">↓</div>}</React.Fragment>; })}</div>{lifecycle.inventory_movements.length > 0 && <div className="mt-4 rounded-md border border-border bg-card p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Inventory movements · cost basis</div><p className="mt-1 text-[11px] text-muted-foreground">Sale and return movements are shown separately. Inventory value is unit cost × quantity, not the customer refund amount.</p><div className="mt-3 space-y-2">{lifecycle.inventory_movements.map((movement, index) => <div key={String(movement.movement_id ?? index)} className="grid gap-2 rounded-md border border-border bg-background p-2 text-[11px] sm:grid-cols-[auto_1fr_auto_auto_auto]"><span className="font-bold text-foreground">{String(movement.movement_type ?? "MOVEMENT")}</span><span className="font-mono text-muted-foreground">{String(movement.movement_id ?? "Movement")}</span><span className="text-muted-foreground">SKU {String(movement.sku ?? "—")}</span><span className="text-muted-foreground">Qty {String(movement.quantity ?? "—")}</span><span className="text-right font-semibold text-foreground">Unit {formatMinor(movement.unit_cost_minor)} · Value {formatMinor(movement.inventory_value_minor)}</span></div>)}</div></div>}{exceptionType === "AMBIGUOUS_ASSOCIATION" && lifecycle.payments.length > 1 && <div className="mt-3 rounded-md border border-warning/30 bg-warning/5 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-warning">Competing payment candidates</div><div className="mt-2 grid gap-2 sm:grid-cols-2">{lifecycle.payments.slice(0, 4).map((payment, index) => <div key={String(payment.payment_id ?? index)} className="rounded-md border border-warning/20 bg-card p-2 text-[11px]"><div className="font-semibold text-foreground">Payment {String.fromCharCode(65 + index)}</div><div className="mt-1 font-mono text-muted-foreground">{String(payment.payment_id ?? "Candidate")}</div><div className="mt-1 text-muted-foreground">{payment.amount_minor !== undefined ? `${Number(payment.amount_minor) / 100}` : "Amount unavailable"} · {String(payment.captured_at ?? "Time unavailable")}</div></div>)}</div><p className="mt-2 text-[11px] text-muted-foreground">No unique reference establishes which candidate belongs to this order.</p></div>}</div>;
}

function InvestigationStory({ investigation }: { investigation: ApiInvestigation }) {
  const supporting = investigation.supporting_evidence.filter(item => item.verified !== false);
  const contradictory = investigation.contradictory_evidence.filter(item => item.verified !== false);
  const missing = investigation.missing_evidence.length;
  const failed = investigation.status === "FAILED";
  const unresolved = investigation.status === "UNRESOLVED";
  return <div className="mt-4 space-y-3 rounded-lg border border-border p-4"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Evidence assessment</div>{failed ? <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3"><div className="text-sm font-bold text-destructive">Investigation failed</div><p className="mt-1 text-xs leading-5 text-muted-foreground">The provider/system execution failed. The deterministic finding remains available and has not been changed.</p></div> : unresolved ? <div className="rounded-md border border-warning/40 bg-warning/10 p-3"><div className="text-sm font-bold text-warning">Cannot safely resolve</div><p className="mt-1 text-xs leading-5 text-muted-foreground">{investigation.summary}</p><div className="mt-2 text-[11px] text-muted-foreground">Missing evidence: {investigation.missing_evidence.join("; ") || "Additional corroboration is required."}</div><div className="mt-2 text-[11px] font-semibold text-foreground">Human decision required</div></div> : <div className="rounded-md border border-success/30 bg-success/5 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-success">Explained</div><div className="mt-1 text-sm font-bold text-foreground">{investigation.root_cause_code ?? "Structured conclusion"}</div><p className="mt-1 text-xs leading-5 text-muted-foreground">{investigation.summary}</p></div>}<div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Verified evidence</div><div className="mt-2 grid gap-2 sm:grid-cols-4"><div className="rounded-md bg-success/10 p-2"><div className="text-[10px] text-muted-foreground">Supporting</div><div className="text-sm font-bold text-foreground">{supporting.length}</div></div><div className="rounded-md bg-warning/10 p-2"><div className="text-[10px] text-muted-foreground">Contradictory</div><div className="text-sm font-bold text-foreground">{contradictory.length}</div></div><div className="rounded-md bg-muted p-2"><div className="text-[10px] text-muted-foreground">Missing</div><div className="text-sm font-bold text-foreground">{missing}</div></div><div className="rounded-md bg-destructive/10 p-2"><div className="text-[10px] text-muted-foreground">Rejected claims</div><div className="text-sm font-bold text-foreground">{investigation.rejected_evidence.length}</div></div></div></div>{!failed && <div className="rounded-md border border-info/30 bg-info/5 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-info">Recommendation</div><div className="mt-1 text-xs font-semibold text-foreground">{investigation.recommended_action_code ?? (unresolved ? "Request controller decision" : "Review with operations")}</div><div className="mt-2 text-[11px] text-muted-foreground">{investigation.requires_human_review ? "A controller decision is required before any action." : "No approval is required from this evidence assessment."}</div></div>}<details className="rounded-md border border-border bg-muted/20 p-3"><summary className="cursor-pointer text-[10px] font-bold uppercase tracking-wide text-muted-foreground">AI investigation trace</summary><div className="mt-3 space-y-3"><div className="text-[11px] font-semibold text-foreground">{investigation.provider} · {investigation.model} · {investigation.status} · {investigation.latency_ms} ms</div><div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Evidence requests</div><div className="mt-2 space-y-2">{investigation.tool_calls.map(call => <div key={`${call.sequence_no}-${call.name}`} className="rounded-md border border-border bg-card p-2 text-[11px]"><div className="font-mono font-semibold text-foreground">{call.sequence_no}. {call.name}</div><div className="mt-1 text-muted-foreground">{call.result_summary}</div></div>)}</div></div><div className="text-[10px] text-muted-foreground">Bounded read-only tools only. Hidden chain-of-thought is not displayed.</div></div></details></div>;
}

function requestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value)) : "Not set";
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, character => character.toUpperCase());
}

function isWorkspaceMetadataColumn(value: string) {
  return value.replaceAll("_", "").toLowerCase() === "organizationid";
}

function errorMessage(error: unknown) {
  if (error instanceof ApiClientError) return error.message;
  return "The request could not be completed. Check that the API is running and try again.";
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "FAILED" ? "destructive" : status === "RECONCILED" || status === "READY" ? "default" : "outline";
  return <Badge variant={tone}>{statusLabel(status)}</Badge>;
}

function reviewActionFor(exceptionType: string | null): ResolutionActionCode {
  if (exceptionType === "REFUND_WITHOUT_INVENTORY_RETURN") return "REQUEST_INVENTORY_VERIFICATION";
  if (exceptionType === "ERP_AMOUNT_MISMATCH" || exceptionType === "ERP_INVOICE_MISSING") return "REQUEST_ERP_INVOICE_CORRECTION";
  if (exceptionType === "MISSING_SETTLEMENT" || exceptionType === "SETTLEMENT_FEE_VARIANCE") return "REQUEST_SETTLEMENT_REVIEW";
  if (exceptionType === "DUPLICATE_PAYMENT" || exceptionType === "AMBIGUOUS_ASSOCIATION") return "REQUEST_PAYMENT_REVIEW";
  if (exceptionType === "INVENTORY_RESTORED_WITHOUT_REFUND") return "REQUEST_PAYMENT_REVIEW";
  if (exceptionType === "INVENTORY_VALUE_MISMATCH" || exceptionType === "INVENTORY_QUANTITY_MISMATCH") return "REQUEST_INVENTORY_VERIFICATION";
  return "REQUEST_REFUND_REVIEW";
}

function isAiEligibleResult(result: ApiReconciliationResult) {
  const type = `${result.exception_type ?? ""} ${result.findings.map(item => item.code).join(" ")}`;
  return type.includes("REFUND") || type.includes("INVENTORY") || type.includes("AMBIGUOUS");
}

function closeStateForResult(result: ApiReconciliationResult, investigation?: ApiInvestigation | null) {
  if (result.status === "AMBIGUOUS") return "NEEDS_HUMAN_DECISION" as const;
  if (investigation?.status === "FAILED") return "FAILED" as const;
  if (investigation?.status === "UNRESOLVED") return "NEEDS_EVIDENCE" as const;
  if (isAiEligibleResult(result)) return "NEEDS_EVIDENCE" as const;
  return "EXPLAINED" as const;
}

function valueMatches(value: unknown, expected: string) {
  return value !== null && value !== undefined && String(value) === expected;
}

function lifecycleFromNormalizedRecords(records: ApiNormalizedRecord[], orderId: string): ApiLifecycleResponse | null {
  const scoped = records.filter(record => valueMatches(record.values.order_id, orderId));
  const orderRecord = scoped.find(record => record.source_type === "ORDERS" || record.source_type === "SALES");
  if (!orderRecord) return null;
  const byType = (sourceType: string) => scoped.filter(record => record.source_type === sourceType).map(record => record.values);
  return {
    organization_id: "",
    order: orderRecord.values,
    payments: byType("PAYMENTS"),
    settlements: scoped.filter(record => record.source_type === "SETTLEMENTS" && (record.values.order_id === orderId || scoped.some(payment => valueMatches(payment.values.payment_id, String(record.values.payment_id))))).map(record => record.values),
    invoices: byType("INVOICES"),
    refunds: scoped.filter(record => record.source_type === "REFUNDS").map(record => record.values),
    inventory_movements: byType("INVENTORY_MOVEMENTS"),
    employee_actions: scoped.filter(record => record.source_type === "EMPLOYEE_ACTIONS" && (valueMatches(record.values.entity_id, orderId) || valueMatches(record.values.order_id, orderId))).map(record => record.values),
  };
}

async function fetchInvestigationLifecycle(investigationId: string, orderId: string) {
  try {
    return await fetchLifecycle(orderId);
  } catch (error) {
    if (!(error instanceof ApiClientError) || error.status !== 404) throw error;
    const dataset = await fetchLatestDataset(investigationId);
    const records = await fetchNormalizedRecords(investigationId, dataset.id);
    const lifecycle = lifecycleFromNormalizedRecords(records, orderId);
    if (!lifecycle) throw error;
    return lifecycle;
  }
}

export function FinancialInvestigationsPage() {
  const [items, setItems] = React.useState<ApiFinancialInvestigation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetchFinancialInvestigations().then(setItems).catch(error => setError(errorMessage(error))).finally(() => setLoading(false));
  }, []);

  const [launching, setLaunching] = React.useState(false);
  const [launchError, setLaunchError] = React.useState<string | null>(null);
  async function launchDemo() {
    setLaunching(true); setLaunchError(null);
    try { const prepared = await launchFlagshipDemo(requestId()); window.location.href = `/?investigation=${encodeURIComponent(prepared.id)}`; }
    catch (error) { setLaunchError(errorMessage(error)); setLaunching(false); }
  }

  return <>
    <PageHeading eyebrow="Financial investigations" title="Start with your financial data" description="Create a controlled investigation workspace for source files, mappings, relationships, and reconciliation outcomes.">
      <Button variant="outline" size="sm" onClick={() => void launchDemo()} disabled={launching}>{launching ? "Preparing flagship demo…" : "Launch Flagship Demo"}</Button>
      <Button asChild size="sm"><Link href="/investigations/new"><Plus className="h-3.5 w-3.5" />New investigation</Link></Button>
    </PageHeading>
    {launchError && <Alert variant="destructive" className="mb-5"><AlertTitle>Flagship demo could not be prepared</AlertTitle><AlertDescription>{launchError}</AlertDescription></Alert>}
    {error && <Alert variant="destructive" className="mb-5"><AlertTitle>Unable to load investigations</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {loading && <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation workspaces…</div>}
    {!loading && !error && items.length === 0 && <Card><CardContent className="flex flex-col items-center px-6 py-16 text-center"><div className="rounded-full bg-primary/10 p-3 text-primary"><FolderSearch className="h-6 w-6" /></div><h2 className="mt-4 text-base font-semibold text-foreground">No investigations yet</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Create an investigation, then upload the exports you want FinTrace to understand. Your source files remain scoped to this workspace.</p><Button asChild className="mt-5" size="sm"><Link href="/investigations/new">Create your first investigation</Link></Button></CardContent></Card>}
    {!loading && !error && items.length > 0 && <div className="grid gap-4">{items.map(item => <Card key={item.id}><CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center"><div className="flex min-w-0 flex-1 items-start gap-3"><div className="rounded-lg bg-primary/10 p-2.5 text-primary"><FolderSearch className="h-5 w-5" /></div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{item.id}</span><StatusBadge status={item.status} /></div><h2 className="mt-1 truncate text-sm font-semibold text-foreground">{item.name}</h2><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description || "No description provided."}</p></div></div><div className="grid grid-cols-3 gap-5 border-t border-border pt-4 text-xs md:border-l md:border-t-0 md:pl-5 md:pt-0"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Period</div><div className="mt-1 font-medium text-foreground">{formatDate(item.period_start)}</div><div className="text-muted-foreground">to {formatDate(item.period_end)}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Sources</div><div className="mt-1 font-bold text-foreground">{item.source_file_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Currency</div><div className="mt-1 font-bold text-foreground">{item.base_currency}</div></div></div><Button asChild variant="outline" size="sm"><Link href={`/investigations/${item.id}`}>Open <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card>)}</div>}
  </>;
}

export function NewFinancialInvestigationPage() {
  const router = useRouter();
  const [form, setForm] = React.useState({ name: "", description: "", period_start: "", period_end: "", base_currency: "INR" });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    const submittedForm = {
      ...form,
      period_start: event.currentTarget.querySelector<HTMLInputElement>("#period-start")?.value || form.period_start,
      period_end: event.currentTarget.querySelector<HTMLInputElement>("#period-end")?.value || form.period_end,
    };
    try {
      const result = await createFinancialInvestigation({ ...submittedForm, description: submittedForm.description || undefined, period_start: submittedForm.period_start || undefined, period_end: submittedForm.period_end || undefined }, requestId());
      router.push(`/investigations/${result.id}/sources`);
    } catch (submitError) {
      setError(errorMessage(submitError));
      setSaving(false);
    }
  }

  return <>
    <div className="mb-5"><Link href="/investigations" className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Back to investigations</Link></div>
    <PageHeading eyebrow="New workspace" title="Create a financial investigation" description="Give this investigation a clear scope. You can add source exports immediately after it is created." />
    {error && <Alert variant="destructive" className="mb-5"><AlertTitle>Investigation was not created</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
     <Card className="max-w-3xl"><CardHeader><CardTitle>Investigation details</CardTitle><CardDescription>These details become the audit and data-lineage boundary for the investigation.</CardDescription></CardHeader><CardContent><form onSubmit={submit} className="space-y-5"><div><label htmlFor="investigation-name" className="text-xs font-semibold text-foreground">Name</label><Input id="investigation-name" required minLength={1} maxLength={200} className="mt-2" placeholder="e.g. August 2026 marketplace close" value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} /></div><div><label htmlFor="investigation-description" className="text-xs font-semibold text-foreground">Description <span className="font-normal text-muted-foreground">(optional)</span></label><Textarea id="investigation-description" maxLength={2000} rows={4} className="mt-2" placeholder="What close, process, or financial question are you investigating?" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} /></div><div className="grid gap-4 sm:grid-cols-3"><div><label htmlFor="period-start" className="text-xs font-semibold text-foreground">Period start</label><Input id="period-start" type="date" required className="mt-2" value={form.period_start} onChange={event => setForm(current => ({ ...current, period_start: event.target.value }))} /></div><div><label htmlFor="period-end" className="text-xs font-semibold text-foreground">Period end</label><Input id="period-end" type="date" required className="mt-2" value={form.period_end} onChange={event => setForm(current => ({ ...current, period_end: event.target.value }))} /></div><div><label htmlFor="base-currency" className="text-xs font-semibold text-foreground">Base currency</label><Select id="base-currency" className="mt-2" value={form.base_currency} onChange={event => setForm(current => ({ ...current, base_currency: event.target.value }))}><option value="INR">INR · Indian Rupee</option><option value="USD">USD · US Dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound Sterling</option></Select></div></div><div className="flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:justify-end"><Button asChild variant="outline" size="sm"><Link href="/investigations">Cancel</Link></Button><Button type="submit" size="sm" disabled={saving}>{saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{saving ? "Creating…" : "Create and add sources"}</Button></div></form></CardContent></Card>
  </>;
}

function SourceFileRow({ investigationId, source, autoReview = false, onDeleted, onChanged }: { investigationId: string; source: ApiSourceFile; autoReview?: boolean; onDeleted: (sourceId: string) => void; onChanged: (source: ApiSourceFile) => void }) {
  const [deleting, setDeleting] = React.useState(false);
  const [analyzing, setAnalyzing] = React.useState(false);
  const [expanded, setExpanded] = React.useState(false);
  const [analysis, setAnalysis] = React.useState<ApiSourceAnalysis | null>(null);
  const [mappings, setMappings] = React.useState<ApiSourceMapping[]>([]);
  const [message, setMessage] = React.useState<string | null>(null);
  async function remove() {
    if (!window.confirm(`Remove ${source.original_filename} from this investigation?`)) return;
    setDeleting(true);
    try { await deleteSourceFile(investigationId, source.id); onDeleted(source.id); } catch { setDeleting(false); }
  }
  const review = React.useCallback(async () => {
    setMessage(null); setAnalyzing(true); setExpanded(true);
    try {
      const [loadedAnalysis] = await Promise.all([source.status === "UPLOADED" ? analyzeSourceFile(investigationId, source.id) : fetchSourceAnalysis(investigationId, source.id), source.status === "UPLOADED" ? Promise.resolve([] as ApiSourceMapping[]) : fetchSourceMappings(investigationId, source.id)]);
      const loadedMappings = await fetchSourceMappings(investigationId, source.id);
      setAnalysis(loadedAnalysis);
      setMappings(loadedMappings);
      onChanged({ ...source, status: source.status === "READY" ? "READY" : "MAPPING_REQUIRED", detected_source_type: loadedAnalysis.source_type, detection_confidence: loadedAnalysis.classification_confidence });
      const complete = loadedMappings.every(mapping => !mapping.required || (mapping.canonical_field && !mapping.ignored));
      if (loadedAnalysis.classification_confidence >= 0.9 && complete && source.status !== "READY") {
        await confirmSourceMappings(investigationId, source.id);
        setMappings(current => current.map(item => ({ ...item, status: "CONFIRMED" })));
        onChanged({ ...source, status: "READY", detected_source_type: loadedAnalysis.source_type, detection_confidence: loadedAnalysis.classification_confidence });
        setExpanded(false);
        setMessage("High-confidence source setup accepted automatically. Review it only if the source looks inconsistent.");
      }
    } catch (reviewError) { setMessage(errorMessage(reviewError)); }
    finally { setAnalyzing(false); }
  }, [investigationId, onChanged, source]);
  React.useEffect(() => {
    if (autoReview && source.status === "MAPPING_REQUIRED" && !analysis && !analyzing) void review();
  }, [analysis, analyzing, autoReview, review, source.status]);
  return <div className="border-b border-border py-4 last:border-b-0"><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="flex min-w-0 flex-1 items-center gap-3"><div className="rounded-md bg-muted p-2 text-muted-foreground">{source.original_filename.toLowerCase().endsWith(".xlsx") ? <FileSpreadsheet className="h-4 w-4" /> : <FileText className="h-4 w-4" />}</div><div className="min-w-0"><div className="truncate text-xs font-semibold text-foreground">{source.original_filename}</div><div className="mt-1 text-[11px] text-muted-foreground">{formatBytes(source.size_bytes)} · {source.row_count.toLocaleString()} rows · {source.column_count} columns</div></div></div><div className="flex items-center gap-2"><StatusBadge status={source.status} /><Button variant="outline" size="sm" onClick={() => { setExpanded(!expanded); if (!expanded && !analysis) void review(); }}>{analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{analysis ? (expanded ? "Hide mapping" : "Review mapping") : source.status === "UPLOADED" || source.status === "FAILED" ? "Analyze source" : "Review mapping"}</Button><Button variant="ghost" size="icon" aria-label={`Remove ${source.original_filename}`} onClick={remove} disabled={deleting}>{deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}</Button></div></div>{message && <Alert variant="destructive" className="mt-3"><AlertDescription>{message}</AlertDescription></Alert>}{expanded && analysis && <MappingReview investigationId={investigationId} source={source} analysis={analysis} mappings={mappings} onMappings={setMappings} onChanged={onChanged} />}</div>;
}

function MappingReview({ investigationId, source, analysis, mappings, onMappings, onChanged }: { investigationId: string; source: ApiSourceFile; analysis: ApiSourceAnalysis; mappings: ApiSourceMapping[]; onMappings: React.Dispatch<React.SetStateAction<ApiSourceMapping[]>>; onChanged: (source: ApiSourceFile) => void }) {
  const [saving, setSaving] = React.useState<string | null>(null);
  const [confirming, setConfirming] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  async function save(mapping: ApiSourceMapping, canonical_field: string, ignored: boolean) {
    setSaving(mapping.id); setError(null);
    try { const updated = await editSourceMapping(investigationId, source.id, mapping.id, { canonical_field: canonical_field || null, ignored }); onMappings(current => current.map(item => item.id === updated.id ? updated : item)); }
    catch (saveError) { setError(errorMessage(saveError)); } finally { setSaving(null); }
  }
  async function confirm() {
    setConfirming(true); setError(null); setNotice(null);
    try { await confirmSourceMappings(investigationId, source.id); onMappings(current => current.map(item => ({ ...item, status: "CONFIRMED" }))); onChanged({ ...source, status: "READY" }); setNotice("Required mappings confirmed. Relationship review is the next controlled stage."); }
    catch (confirmError) { setError(errorMessage(confirmError)); } finally { setConfirming(false); }
  }
  async function classify(event: React.ChangeEvent<HTMLSelectElement>) {
    setSaving("classification"); setError(null);
    try { const updated = await updateSourceClassification(investigationId, source.id, event.target.value as SourceType); onChanged({ ...source, detected_source_type: updated.source_type, detection_confidence: updated.classification_confidence, status: "MAPPING_REQUIRED" }); }
    catch (classifyError) { setError(errorMessage(classifyError)); } finally { setSaving(null); }
  }
  const missing = mappings.filter(mapping => mapping.required && (!mapping.canonical_field || mapping.ignored));
  return <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-xs font-semibold text-foreground">Source understanding</div><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{analysis.reasoning_summary}</p><div className="mt-2 flex flex-wrap gap-2 text-[10px] font-semibold"><Badge variant={analysis.provider_status === "AI_PROVIDER" ? "default" : analysis.provider_status === "AI_PROVIDER_UNAVAILABLE" ? "destructive" : "outline"}>{analysis.provider_status === "AI_PROVIDER" ? "Live provider" : analysis.provider_status === "AI_PROVIDER_UNAVAILABLE" ? "AI provider unavailable" : "Offline deterministic analysis"}</Badge><span className="rounded border border-border px-2 py-1">{analysis.provider} · {analysis.model}</span><span className="rounded border border-border px-2 py-1">{Math.round(analysis.classification_confidence * 100)}% proposal confidence</span></div><p className="mt-2 text-[10px] text-muted-foreground">Only bounded source metadata is used for this proposal; raw files are not sent to an AI provider.</p></div><label className="text-[11px] font-semibold text-foreground">Source type<Select className="mt-1 min-w-44" value={analysis.source_type} onChange={classify} disabled={saving === "classification"}><option value="UNKNOWN">Unknown</option>{["SALES", "ORDERS", "PAYMENTS", "SETTLEMENTS", "REFUNDS", "INVOICES", "INVENTORY_MOVEMENTS", "EMPLOYEE_ACTIONS"].map(type => <option key={type} value={type}>{statusLabel(type)}</option>)}</Select></label></div><div className="mt-4 space-y-2">{mappings.map(mapping => { const workspaceMetadata = isWorkspaceMetadataColumn(mapping.source_column); const canonicalOptions = canonicalFieldsBySourceType[analysis.source_type]; return <div key={mapping.id} className="grid gap-2 rounded-md border border-border bg-background p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-center"><div><div className="text-xs font-medium text-foreground">{mapping.source_column}{mapping.required && <span className="ml-1 text-destructive">Required</span>}</div><div className="text-[10px] text-muted-foreground">{workspaceMetadata ? "Workspace scope · managed automatically" : `${mapping.inferred_type} · ${Math.round(mapping.confidence * 100)}% proposal`}</div></div>{workspaceMetadata ? <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">Applied from signed workspace identity</div> : <Select aria-label={`Canonical field for ${mapping.source_column}`} value={mapping.canonical_field ?? ""} onChange={event => { const canonical = event.target.value; onMappings(current => current.map(item => item.id === mapping.id ? { ...item, canonical_field: canonical || null, ignored: canonical === "" } : item)); void save(mapping, canonical, canonical === ""); }} disabled={saving === mapping.id || source.status === "READY"}><option value="">Ignore this column</option>{canonicalOptions.map(field => <option key={field} value={field}>{field.replaceAll("_", " ")}</option>)}</Select>}<span className="text-center text-[11px] font-semibold text-muted-foreground">{workspaceMetadata ? "System field" : <Button variant="outline" size="sm" onClick={() => void save(mapping, "", true)} disabled={saving === mapping.id || source.status === "READY"}>Ignore</Button>}</span></div>; })}</div>{missing.length > 0 && <p className="mt-3 text-[11px] text-warning">{missing.length} required mapping(s) still need a canonical field.</p>}{error && <Alert variant="destructive" className="mt-3"><AlertDescription>{error}</AlertDescription></Alert>}{notice && <Alert variant="info" className="mt-3"><AlertDescription>{notice}</AlertDescription></Alert>}<div className="mt-4 flex items-center justify-between">{source.status === "READY" ? <span className="text-[11px] font-semibold text-success">High-confidence source setup accepted. Review again only if the source looks inconsistent.</span> : <><span className="text-[11px] text-muted-foreground">Only uncertain or incomplete mappings need your review.</span><Button size="sm" onClick={() => void confirm()} disabled={confirming || missing.length > 0}>{confirming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{confirming ? "Confirming…" : "Confirm source setup"}</Button></>}</div></div>;
}

export function RelationshipReview({ investigationId }: { investigationId: string }) {
  const [items, setItems] = React.useState<ApiRelationshipProposal[]>([]);
  const [sources, setSources] = React.useState<ApiSourceFile[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchRelationships(investigationId).then(setItems).catch(() => undefined).finally(() => setLoading(false)); fetchSourceFiles(investigationId).then(setSources).catch(() => undefined); }, [investigationId]);
  async function discover() { setWorking(true); setError(null); try { const proposals = await discoverRelationships(investigationId); const safelyAccepted = proposals.filter(item => item.status === "PROPOSED" && item.confidence >= 0.9 && item.value_overlap_percent >= 99 && item.duplicate_key_rate_percent === 0 && (item.amount_agreement_percent === null || item.amount_agreement_percent >= 95) && (item.temporal_consistency_percent === null || item.temporal_consistency_percent >= 95)); const accepted = await Promise.all(safelyAccepted.map(item => decideRelationship(investigationId, item.id, "ACCEPTED"))); const acceptedById = new Map(accepted.map(item => [item.id, item])); setItems(proposals.map(item => acceptedById.get(item.id) ?? item)); } catch (discoverError) { setError(errorMessage(discoverError)); } finally { setWorking(false); } }
  async function decide(item: ApiRelationshipProposal, status: "ACCEPTED" | "REJECTED") { setWorking(true); try { const updated = await decideRelationship(investigationId, item.id, status); setItems(current => current.map(candidate => candidate.id === updated.id ? updated : candidate)); } catch (decisionError) { setError(errorMessage(decisionError)); } finally { setWorking(false); } }
  const sourceName = (id: string) => sources.find(source => source.id === id)?.original_filename ?? id;
  return <Card className="mt-4"><CardHeader><CardTitle>Source relationships</CardTitle><CardDescription>High-confidence links are accepted when overlap, cardinality, duplicates, and consistency agree. Only conflicting or ambiguous links need your decision.</CardDescription></CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{loading ? <div role="status" className="text-xs text-muted-foreground">Loading relationship proposals…</div> : items.length === 0 ? <div className="flex flex-col items-start gap-3"><p className="text-xs text-muted-foreground">No links yet. Discover relationships after source setup is complete.</p><Button size="sm" onClick={() => void discover()} disabled={working}>Discover relationships</Button></div> : <div className="space-y-3"><div className="rounded-md border border-success/20 bg-success/5 p-3 text-[11px] text-muted-foreground">{items.filter(item => item.status === "ACCEPTED").length} relationship{items.filter(item => item.status === "ACCEPTED").length === 1 ? "" : "s"} accepted · {items.filter(item => item.status === "PROPOSED").length} need review</div>{items.map(item => { const needsReview = item.status === "PROPOSED" && (item.duplicate_key_rate_percent > 0 || item.value_overlap_percent < 99 || (item.amount_agreement_percent !== null && item.amount_agreement_percent < 95) || (item.temporal_consistency_percent !== null && item.temporal_consistency_percent < 95)); return <div key={item.id} className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><div className="text-xs font-semibold text-foreground">{sourceName(item.source_file_id)} <span className="mx-1 text-muted-foreground">↕</span> {sourceName(item.target_source_file_id)}</div><div className="mt-1 text-[11px] text-muted-foreground">{item.join_fields.join(", ")} · relationship evidence</div><div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-muted-foreground sm:grid-cols-4"><span>Overlap {item.value_overlap_percent.toFixed(1)}%</span><span>Cardinality {item.cardinality}</span><span>Duplicates {item.duplicate_key_rate_percent.toFixed(1)}%</span><span>Temporal {item.temporal_consistency_percent === null ? "—" : `${item.temporal_consistency_percent.toFixed(1)}%`}</span>{item.amount_agreement_percent !== null && <span>Amount {item.amount_agreement_percent.toFixed(1)}%</span>}</div>{needsReview && <p className="mt-2 text-[11px] font-semibold text-warning">Review required: duplicate or conflicting relationship evidence.</p>}</div><div className="flex items-center gap-2"><StatusBadge status={item.status} />{item.status === "PROPOSED" && <><Button variant="outline" size="sm" onClick={() => void decide(item, "REJECTED")} disabled={working}>Reject</Button><Button size="sm" onClick={() => void decide(item, "ACCEPTED")} disabled={working}>Accept</Button></>}</div></div>; })}</div>}</CardContent></Card>;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ReconciliationRunPanelSummary({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [providerHealth, setProviderHealth] = React.useState<ApiProviderHealth | null>(null);
  const load = React.useCallback(() => fetchLatestReconciliation(investigationId).then(loaded => { setRun(loaded); return fetchReconciliationResults(investigationId, loaded.id); }).then(loaded => { setResults(loaded); setSelectedId(current => current ?? loaded.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null); }).catch(() => undefined), [investigationId]);
  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => { fetchProviderHealth().then(setProviderHealth).catch(() => setProviderHealth({ status: "UNAVAILABLE", provider: "unknown", model: "unknown", configured: false, latency_ms: 0, error_category: "health_check_failed", retryable: true, detail: "Provider health could not be checked.", overall_status: "UNAVAILABLE", active_provider: null, providers: [] })); }, []);
  const selected = results.find(item => item.id === selectedId) ?? null;
  async function inspect(result: ApiReconciliationResult) { if (!run) return; setSelectedId(result.id); setWorking(true); setError(null); try { setInvestigation(await fetchReconciliationInvestigation(investigationId, run.id, result.id)); } catch { setInvestigation(null); } finally { setWorking(false); } }
  async function investigate() { if (!run || !selected) return; setWorking(true); setError(null); try { setInvestigation(await investigateReconciliationResult(investigationId, run.id, selected.id)); } catch (cause) { setError(errorMessage(cause)); } finally { setWorking(false); } }
  return <Card className="mt-4"><CardHeader><CardTitle>Deterministic reconciliation</CardTitle><CardDescription>The immutable dataset is reconciled by code. AI only investigates the exceptions after this run, and every provider claim is verified before it can be supported.</CardDescription>{providerHealth && <ProviderHealthSummary health={providerHealth} />}</CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{run ? <><div className="grid gap-3 sm:grid-cols-5"><MetricCell label="Lifecycles" value={run.lifecycle_count.toLocaleString()} /><MetricCell label="Reconciled" value={run.reconciled_count.toLocaleString()} /><MetricCell label="Variance" value={results.filter(item => item.status === "RECONCILED_WITH_VARIANCE").length.toLocaleString()} /><MetricCell label="Exceptions" value={(run.exception_count + run.ambiguous_count).toLocaleString()} /><MetricCell label="Potential exposure" value={(run.open_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })} /></div><div className="mt-3 rounded-md border border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">Input accounting: {run.records_consumed.toLocaleString()} consumed / {run.records_expected.toLocaleString()} expected · {run.status}{run.failure_reason ? ` · ${run.failure_reason}` : ""}</div></> : <p className="text-xs text-muted-foreground">No reconciliation run exists for this investigation yet.</p>}{results.length > 0 && <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]"><div className="max-h-80 space-y-2 overflow-auto pr-1">{results.filter(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS").map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className={`w-full rounded-md border p-3 text-left text-xs ${selected?.id === item.id ? "border-primary bg-primary/5" : "border-border bg-muted/20"}`}><div className="flex items-center justify-between gap-2"><span className="font-semibold text-foreground">{item.order_id}</span><StatusBadge status={item.status} /></div><div className="mt-1 text-[11px] text-muted-foreground">{item.exception_type ?? "AMBIGUOUS"} · {item.exposure_category} · associated {item.exposure_minor.toLocaleString()} minor units</div></Button>)}</div>{selected && <div className="rounded-md border border-border p-4 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><div><div className="font-semibold text-foreground">AI INVESTIGATION · {selected.exception_type ?? "AMBIGUOUS"}</div><div className="mt-1 text-[11px] text-muted-foreground">Lifecycle {selected.order_id} · deterministic findings: {selected.findings.map(item => item.code).join(", ")}</div></div><Button size="sm" onClick={() => void investigate()} disabled={working}>{working ? "Investigating…" : investigation ? "Re-run investigation" : "Investigate with AI"}</Button></div>{investigation ? <><div className="mt-3 rounded-md border border-border bg-muted/20 p-3 text-[11px] font-semibold text-foreground">{investigation.provider} · {investigation.model} · {investigation.status === "FAILED" ? "provider unavailable" : "completed"} · {investigation.latency_ms} ms</div><p className="mt-3 leading-5 text-muted-foreground">{investigation.summary}</p>{investigation.fallback_used && <div className="mt-2 rounded-md border border-warning/30 bg-warning/5 p-3 text-[11px] text-muted-foreground">{investigation.originally_requested_provider} unavailable · investigation completed with {investigation.actual_provider_used} fallback</div>}{investigation.status === "FAILED" && <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-[11px] text-muted-foreground">Provider failure: {investigation.provider_error_category ?? "unknown"} · retryable {investigation.provider_retryable ? "yes" : "no"} · stage {investigation.failure_stage ?? "unknown"} · iteration {investigation.failure_iteration ?? "n/a"}</div>}<div className="mt-3 grid gap-3 sm:grid-cols-3"><div><div className="text-[10px] uppercase text-muted-foreground">Root cause</div><div className="mt-1 font-semibold text-foreground">{investigation.root_cause_code ?? "UNRESOLVED"}</div></div><div><div className="text-[10px] uppercase text-muted-foreground">Evidence score</div><div className="mt-1 font-semibold text-foreground">{investigation.evidence_score}/100</div></div><div><div className="text-[10px] uppercase text-muted-foreground">Verifier</div><div className="mt-1 font-semibold text-foreground">{investigation.verifier_passed ? "Passed" : "Review required"}</div></div></div><EvidencePanel title="Supporting evidence" items={investigation.supporting_evidence} /><EvidencePanel title="Contradictory evidence" items={investigation.contradictory_evidence} /><div className="mt-3"><div className="font-semibold text-foreground">Missing evidence</div>{investigation.missing_evidence.length ? <ul className="mt-1 list-disc space-y-1 pl-4 text-muted-foreground">{investigation.missing_evidence.map(item => <li key={item}>{item}</li>)}</ul> : <div className="mt-1 text-muted-foreground">None recorded.</div>}</div>{investigation.rejected_evidence.length > 0 && <EvidencePanel title="Verification issues" items={investigation.rejected_evidence} />}{investigation.tool_calls.length > 0 && <div className="mt-3 border-t border-border pt-3"><div className="font-semibold text-foreground">Bounded tool trace</div><div className="mt-2 space-y-1 text-muted-foreground">{investigation.tool_calls.map(call => <div key={`${call.sequence_no}-${call.name}`}><span className="font-semibold text-foreground">{call.sequence_no}. {call.name}</span> · {call.result_summary} · {call.duration_ms} ms</div>)}</div></div>}</> : <p className="mt-6 text-center text-xs text-muted-foreground">Select an exception and run the bounded provider investigation.</p>}</div>}</div>}</CardContent></Card>;
}

function ProviderHealthSummary({ health }: { health: ApiProviderHealth }) {
  const tone = health.overall_status === "AVAILABLE" ? "border-success/30 bg-success/5" : health.overall_status === "DEGRADED" ? "border-warning/30 bg-warning/5" : "border-destructive/30 bg-destructive/5";
  return <div className={`mt-3 rounded-md border p-3 text-[11px] ${tone}`}><div className="font-semibold text-foreground">{health.overall_status === "AVAILABLE" ? "AI ready" : health.overall_status === "DEGRADED" ? "AI ready · fallback available" : "AI unavailable"}</div><div className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">{health.providers.map(item => <div key={`${item.provider}-${item.model}`}><span className="font-semibold text-foreground">{item.provider === "gemini" ? "Primary" : "Fallback"}</span> · {item.provider} · {item.model} · {item.status === "CONNECTED" ? "Connected" : item.status === "NOT_CONFIGURED" ? "Not configured" : `Unavailable${item.error_category ? ` · ${item.error_category}` : ""}`}</div>)}</div></div>;
}

function MetricCell({ label, value }: { label: string; value: string }) { return <div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div><div className="mt-1 text-lg font-bold text-foreground">{value}</div></div>; }
function EvidencePanel({ title, items }: { title: string; items: { source: string; record_id?: string | null; fact: string; verification_issue?: string | null }[] }) { return <div className="mt-3"><div className="font-semibold text-foreground">{title}</div>{items.length ? <div className="mt-1 space-y-1 text-muted-foreground">{items.map((item, index) => <div key={`${item.source}-${item.record_id ?? "missing"}-${index}`}>{item.source}{item.record_id ? ` · ${item.record_id}` : " · no record"} · {item.fact}{item.verification_issue ? ` · ${item.verification_issue}` : ""}</div>)}</div> : <div className="mt-1 text-muted-foreground">None recorded.</div>}</div>; }

function ReconciliationStory({ run, results, currency }: { run: ApiReconciliationRun; results: ApiReconciliationResult[]; currency: string }) {
  const count = (status: string) => results.filter(item => item.status === status).length;
  const categories = ["POTENTIAL_EXPOSURE", "TIMING_VARIANCE", "DATA_QUALITY", "CONTROL_RISK"];
  const categoryCount = (category: string) => results.reduce((total, item) => total + item.findings.filter(finding => finding.exposure_category === category).length, 0);
  const explained = results.filter(item => item.status === "EXCEPTION" && !isAiEligibleResult(item)).length;
  const needsEvidence = results.filter(item => item.status === "EXCEPTION" && isAiEligibleResult(item)).length;
  const needsDecision = results.filter(item => item.status === "AMBIGUOUS").length;
  const cleanReconciled = run.reconciled_count - count("RECONCILED_WITH_VARIANCE");
  return <div className="rounded-lg border border-border p-4"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Financial close status</div><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-6"><MetricCell label="Reconciled" value={cleanReconciled.toLocaleString()} /><MetricCell label="Expected variance" value={count("RECONCILED_WITH_VARIANCE").toLocaleString()} /><MetricCell label="Explained" value={explained.toLocaleString()} /><MetricCell label="Needs evidence" value={needsEvidence.toLocaleString()} /><MetricCell label="Needs human decision" value={needsDecision.toLocaleString()} /><MetricCell label="Potential exposure" value={((run.open_exposure_minor ?? 0) / 100).toLocaleString("en-IN", { style: "currency", currency })} /></div><div className="mt-4 border-t border-border pt-4"><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Input integrity</div><div className="mt-2 text-lg font-bold text-foreground">{run.records_loaded.toLocaleString()} / {run.records_expected.toLocaleString()} normalized records accounted for</div><div className="mt-1 text-[11px] text-muted-foreground">{run.records_loaded.toLocaleString()} loaded · {run.records_consumed.toLocaleString()} consumed · {run.rejected_record_count.toLocaleString()} rejected · {run.orphan_record_count.toLocaleString()} orphaned</div></div><div className="mt-4 border-t border-border pt-4"><div className="flex items-center justify-between gap-3"><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Risk categories</div><span className="text-[10px] text-muted-foreground">Finding counts; categories may overlap.</span></div><div className="mt-2 grid gap-2 sm:grid-cols-4">{categories.map(category => <div key={category} className="rounded-md border border-border p-3"><div className="text-[10px] text-muted-foreground">{displayStatus(category)}</div><div className="mt-1 text-lg font-bold text-foreground">{categoryCount(category).toLocaleString()}</div></div>)}</div></div></div>;
}

// Kept as a compatibility reference while the uploaded-investigation panel is the primary flow.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyReconciliationRunPanel({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [patterns, setPatterns] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [investigated, setInvestigated] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [reviewRequest, setReviewRequest] = React.useState<ApiResolutionRequest | null>(null);
  const [requestingReview, setRequestingReview] = React.useState(false);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchLatestReconciliation(investigationId).then(loaded => { setRun(loaded); return Promise.all([fetchReconciliationResults(investigationId, loaded.id), fetchFinancialInvestigationPatterns(investigationId)]); }).then(([loadedResults, loadedPatterns]) => { setResults(loadedResults); setPatterns(loadedPatterns); const existing = loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS"); return existing ? fetchReconciliationInvestigation(investigationId, existing.run_id, existing.id).then(loadedInvestigation => { setInvestigation(loadedInvestigation); setInvestigated(loadedInvestigation.status); }).catch(() => undefined) : undefined; }).catch(() => undefined); }, [investigationId]);
  async function reconcile() {
    setWorking(true); setError(null);
    try {
      const dataset = await normalizeDataset(investigationId);
      const completed = await runInvestigationReconciliation(investigationId, dataset.id);
      setRun(completed); const [loadedResults, loadedPatterns] = await Promise.all([fetchReconciliationResults(investigationId, completed.id), fetchFinancialInvestigationPatterns(investigationId)]); setResults(loadedResults); setPatterns(loadedPatterns);
    } catch (runError) { setError(errorMessage(runError)); } finally { setWorking(false); }
  }
  async function investigate() {
    const result = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
    if (!run || !result) return;
    setWorking(true); setError(null);
    try { const response = await investigateReconciliationResult(investigationId, run.id, result.id); setInvestigated(response.status); setInvestigation(response); }
    catch (investigateError) { setError(errorMessage(investigateError)); } finally { setWorking(false); }
  }
  async function requestReview() {
    const result = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
    if (!run || !result) return;
    setRequestingReview(true); setError(null);
    try { setReviewRequest(await requestFinancialResolution(investigationId, run.id, result.id, reviewActionFor(result.exception_type), requestId())); }
    catch (reviewError) { setError(errorMessage(reviewError)); }
    finally { setRequestingReview(false); }
  }
  const exception = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
  return <Card className="mt-4"><CardHeader><CardTitle>Deterministic reconciliation</CardTitle><CardDescription>Normalize the confirmed sources into an immutable dataset, then run the deterministic lifecycle rules. No AI call changes this result.</CardDescription></CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{run ? <div className="grid gap-3 sm:grid-cols-4"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Lifecycles</div><div className="mt-1 text-xl font-bold text-foreground">{run.lifecycle_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Reconciled</div><div className="mt-1 text-xl font-bold text-foreground">{run.reconciled_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Exceptions</div><div className="mt-1 text-xl font-bold text-warning">{run.exception_count + run.ambiguous_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Exposure</div><div className="mt-1 text-xl font-bold text-foreground">{(run.open_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })}</div></div></div> : <p className="text-xs text-muted-foreground">No reconciliation run exists for this investigation yet.</p>}{patterns.length > 0 && <div className="mt-4 rounded-md border border-border bg-muted/20 p-3 text-xs"><div className="font-semibold text-foreground">Advisory recurring signals</div>{patterns.map(pattern => <div key={pattern.pattern_id} className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground"><span className="font-semibold text-foreground">{pattern.exception_type}</span><span>·</span><span>{pattern.occurrence_count} occurrences</span><span>·</span><span>{(pattern.associated_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })} exposure</span></div>)}</div>}{exception && <div className="mt-4 flex flex-col gap-2 rounded-md border border-border bg-muted/20 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"><span><span className="font-semibold text-foreground">{exception.order_id}</span> · {exception.exception_type ?? "Ambiguous result"} · requires bounded evidence review</span><div className="flex flex-wrap items-center gap-2"><Button variant="outline" size="sm" onClick={() => void investigate()} disabled={working || investigated !== null}>{investigated ? `Investigation ${investigated.toLowerCase()}` : "Investigate exception"}</Button><Button size="sm" onClick={() => void requestReview()} disabled={working || requestingReview || reviewRequest !== null}>{requestingReview ? "Requesting review…" : reviewRequest ? "Review requested" : "Request human review"}</Button></div></div>}{investigation && <div className="mt-4 rounded-md border border-border p-4 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-semibold text-foreground">Evidence investigation</div><StatusBadge status={investigation.status} /></div><p className="mt-2 leading-5 text-muted-foreground">{investigation.summary}</p>{investigation.status === "FAILED" && <Alert variant="destructive" className="mt-3"><AlertDescription>AI provider unavailable. Deterministic evidence remains available for manual review.</AlertDescription></Alert>}<div className="mt-3 grid gap-3 sm:grid-cols-3"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Evidence score</div><div className="mt-1 font-bold text-foreground">{investigation.evidence_score}/100</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Root cause</div><div className="mt-1 font-semibold text-foreground">{investigation.root_cause_code ?? "Unresolved"}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Review</div><div className="mt-1 font-semibold text-foreground">{investigation.requires_human_review ? "Human review required" : "No review required"}</div></div></div>{investigation.tool_calls.length > 0 && <div className="mt-3 border-t border-border pt-3"><div className="font-semibold text-foreground">Read-only evidence trace</div><div className="mt-2 space-y-1 text-muted-foreground">{investigation.tool_calls.map(call => <div key={`${call.name}-${call.target}`} className="flex flex-wrap gap-x-2"><span className="font-medium text-foreground">{call.name}</span><span>{call.target}</span><span>· {call.status}</span><span>· {call.duration_ms} ms</span></div>)}</div></div>}</div>}{reviewRequest && <Alert variant="info" className="mt-4"><AlertTitle>Human review requested</AlertTitle><AlertDescription>{reviewRequest.action_code} is pending approval. The financial state has not been changed.</AlertDescription></Alert>}<Button className="mt-4" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{working ? "Processing…" : run ? "Run again" : "Normalize and reconcile"}</Button></CardContent></Card>;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ReconciliationRunPanelLegacy({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [patterns, setPatterns] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [lifecycle, setLifecycle] = React.useState<ApiLifecycleResponse | null>(null);
  const [reviewRequest, setReviewRequest] = React.useState<ApiResolutionRequest | null>(null);
  const [providerHealth, setProviderHealth] = React.useState<ApiProviderHealth | null>(null);
  const [working, setWorking] = React.useState(false);
  const [requestingReview, setRequestingReview] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const loadedRun = await fetchLatestReconciliation(investigationId);
      const [loadedResults, loadedPatterns] = await Promise.all([
        fetchReconciliationResults(investigationId, loadedRun.id),
        fetchFinancialInvestigationPatterns(investigationId),
      ]);
      setRun(loadedRun);
      setResults(loadedResults);
      setPatterns(loadedPatterns);
      setSelectedId(current => current ?? loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null);
    } catch (loadError) {
      if (loadError instanceof ApiClientError && loadError.status === 404) {
        setRun(null);
        setResults([]);
        setPatterns([]);
        return;
      }
      setError(errorMessage(loadError));
    }
  }, [investigationId]);

  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => {
    fetchProviderHealth().then(setProviderHealth).catch(() => setProviderHealth(null));
  }, []);

  const selected = results.find(item => item.id === selectedId) ?? null;
  const exceptions = results.filter(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");

  async function reconcile() {
    setWorking(true); setError(null);
    try {
      const dataset = await normalizeDataset(investigationId);
      const completed = await runInvestigationReconciliation(investigationId, dataset.id);
      const [loadedResults, loadedPatterns] = await Promise.all([
        fetchReconciliationResults(investigationId, completed.id),
        fetchFinancialInvestigationPatterns(investigationId),
      ]);
      setRun(completed); setResults(loadedResults); setPatterns(loadedPatterns);
      setSelectedId(loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null);
      setInvestigation(null); setLifecycle(null); setReviewRequest(null);
    } catch (runError) { setError(errorMessage(runError)); }
    finally { setWorking(false); }
  }

  async function inspect(result: ApiReconciliationResult) {
    if (!run) return;
    setSelectedId(result.id); setInvestigation(null); setLifecycle(null); setReviewRequest(null); setError(null); setWorking(true);
    try {
      const [loadedInvestigation, loadedLifecycle] = await Promise.allSettled([
        fetchReconciliationInvestigation(investigationId, run.id, result.id),
        fetchLifecycle(result.order_id),
      ]);
      if (loadedInvestigation.status === "fulfilled") setInvestigation(loadedInvestigation.value);
      if (loadedLifecycle.status === "fulfilled") setLifecycle(loadedLifecycle.value);
      const failed = [loadedInvestigation, loadedLifecycle].find(
        item => item.status === "rejected" && !(item.reason instanceof ApiClientError && item.reason.status === 404),
      );
      if (failed?.status === "rejected") setError(errorMessage(failed.reason));
    }
    finally { setWorking(false); }
  }

  async function investigate() {
    if (!run || !selected) return;
    setWorking(true); setError(null);
    try { setInvestigation(await investigateReconciliationResult(investigationId, run.id, selected.id)); }
    catch (investigateError) { setError(errorMessage(investigateError)); }
    finally { setWorking(false); }
  }

  async function requestReview() {
    if (!run || !selected) return;
    setRequestingReview(true); setError(null);
    try { setReviewRequest(await requestFinancialResolution(investigationId, run.id, selected.id, reviewActionFor(selected.exception_type), requestId())); }
    catch (reviewError) { setError(errorMessage(reviewError)); }
    finally { setRequestingReview(false); }
  }

  async function decideReview(decision: "approve" | "reject") {
    if (!reviewRequest) return;
    setWorking(true); setError(null);
    try {
      const result = decision === "approve"
        ? await approveResolution(reviewRequest.request_id, requestId())
        : await rejectResolution(reviewRequest.request_id, requestId());
      setReviewRequest(current => current ? { ...current, status: result.request_status, approvals_received: result.approvals_received } : current);
    } catch (decisionError) { setError(errorMessage(decisionError)); }
    finally { setWorking(false); }
  }

  const actor = currentActor();
  const canApprove = actor.role === "FINANCE_MANAGER" || actor.role === "CONTROLLER";
  return <Card id="reconciliation" className="mt-4"><CardHeader><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle>Reconciliation and investigation</CardTitle><CardDescription>Deterministic rules establish the financial result. AI only investigates selected exceptions using read-only, verifiable evidence.</CardDescription></div>{run && <Button variant="outline" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? "Running…" : "Run again"}</Button>}</div>{providerHealth && <ProviderHealthSummary health={providerHealth} />}</CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{!run ? <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center"><div className="text-sm font-semibold text-foreground">Ready to reconcile</div><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted-foreground">Normalize the confirmed source mappings into an immutable dataset, then run the deterministic lifecycle checks. This creates the exception queue for evidence review.</p><Button className="mt-4" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{working ? "Preparing run…" : "Normalize and reconcile"}</Button></div> : <><ReconciliationStory run={run} results={results} currency={currency} /><div className="mt-4 rounded-md border border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">Input integrity: {run.records_loaded.toLocaleString()} / {run.records_expected.toLocaleString()} normalized records accounted for · consumed {run.records_consumed.toLocaleString()} · rejected {run.rejected_record_count.toLocaleString()} · orphan {run.orphan_record_count.toLocaleString()} · {run.failure_reason ?? "No integrity exceptions."}</div>{patterns.length > 0 && <div className="mt-4 rounded-md border border-border p-3 text-xs"><div className="font-semibold text-foreground">Recurring signals</div><div className="mt-2 grid gap-2 sm:grid-cols-2">{patterns.map(pattern => <div key={pattern.pattern_id} className="rounded-md bg-muted/20 p-2 text-muted-foreground"><span className="font-semibold text-foreground">{statusLabel(pattern.exception_type)}</span> · {pattern.occurrence_count} occurrences · {(Number(pattern.associated_exposure_minor) / 100).toLocaleString("en-IN", { style: "currency", currency })}</div>)}</div></div>}{exceptions.length === 0 ? <Alert variant="info" className="mt-4"><AlertTitle>All lifecycles reconciled</AlertTitle><AlertDescription>No exception or ambiguous association requires investigation in this run.</AlertDescription></Alert> : <div id="exceptions" className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.4fr)]"><div><div className="mb-2 flex items-center justify-between"><div className="text-xs font-semibold text-foreground">Top exception categories</div><span className="text-[11px] text-muted-foreground">{exceptions.length} result(s)</span></div><div className="max-h-96 space-y-2 overflow-auto pr-1">{exceptions.map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className={`w-full rounded-md border p-3 text-left text-xs ${selected?.id === item.id ? "border-primary bg-primary/5" : "border-border bg-muted/20"}`}><div className="flex items-center justify-between gap-2"><span className="font-semibold text-foreground">{item.order_id}</span><StatusBadge status={item.status} /></div><div className="mt-1 text-[11px] text-muted-foreground">{statusLabel(item.exception_type ?? "AMBIGUOUS_ASSOCIATION")} · {statusLabel(item.severity)} · {(item.exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })}</div></Button>)}</div></div>{selected && <div className="rounded-md border border-border p-4 text-xs"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="font-semibold text-foreground">Exception investigation</div><div className="mt-1 text-[11px] text-muted-foreground">{selected.order_id} · {statusLabel(selected.exception_type ?? "AMBIGUOUS_ASSOCIATION")} · deterministic findings: {selected.findings.map(item => item.code).join(", ")}</div></div><Button size="sm" onClick={() => void investigate()} disabled={working}>{working ? "Investigating…" : investigation ? "Re-run investigation" : "Investigate with AI"}</Button></div>{lifecycle && <LifecyclePreview lifecycle={lifecycle} exceptionType={selected.exception_type} />}{investigation ? <><InvestigationStory investigation={investigation} /><div className="mt-3 grid gap-3 sm:grid-cols-3"><MetricCell label="Root cause" value={investigation.root_cause_code ?? "Unresolved"} /><MetricCell label="Evidence score" value={`${investigation.evidence_score}/100`} /><MetricCell label="Verifier" value={investigation.verifier_passed ? "Passed" : "Review required"} /></div><EvidencePanel title="Supporting evidence" items={investigation.supporting_evidence} /><EvidencePanel title="Contradictory evidence" items={investigation.contradictory_evidence} />{investigation.rejected_evidence.length > 0 && <EvidencePanel title="Rejected evidence" items={investigation.rejected_evidence} />}</> : <p className="mt-6 text-center text-xs text-muted-foreground">Select “Investigate with AI” to produce a bounded, evidence-backed assessment.</p>}{reviewRequest ? <div className="mt-4 rounded-md border border-info/30 bg-info/5 p-3"><div className="font-semibold text-foreground">Human review · {statusLabel(reviewRequest.status)}</div><div className="mt-1 text-[11px] text-muted-foreground">Requested by {reviewRequest.requester_id} · {reviewRequest.approvals_received}/{reviewRequest.required_approvals} approvals · {statusLabel(reviewRequest.action_code)}</div>{reviewRequest.status === "PENDING_APPROVAL" && (canApprove && actor.id !== reviewRequest.requester_id ? <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={() => void decideReview("approve")} disabled={working}>Approve</Button><Button variant="outline" size="sm" onClick={() => void decideReview("reject")} disabled={working}>Reject</Button></div> : <p className="mt-3 text-[11px] text-muted-foreground">Waiting for a different authorized reviewer. The requester cannot approve their own request.</p>)}</div> : <Button variant="outline" className="mt-4" size="sm" onClick={() => void requestReview()} disabled={working || requestingReview}>{requestingReview ? "Requesting review…" : "Request human review"}</Button>}</div>}</div>}</>}</CardContent></Card>;
}

export function ReconciliationRunPanel({ investigationId, currency, investigationName, periodStart, periodEnd, sourceCount }: { investigationId: string; currency: string; investigationName?: string; periodStart?: string | null; periodEnd?: string | null; sourceCount?: number }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [lifecycle, setLifecycle] = React.useState<ApiLifecycleResponse | null>(null);
  const [reviewRequest, setReviewRequest] = React.useState<ApiResolutionRequest | null>(null);
  const [providerHealth, setProviderHealth] = React.useState<ApiProviderHealth | null>(null);
  const [working, setWorking] = React.useState(false);
  const [requestingReview, setRequestingReview] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const loadedRun = await fetchLatestReconciliation(investigationId);
      const loadedResults = await fetchReconciliationResults(investigationId, loadedRun.id);
      setRun(loadedRun); setResults(loadedResults);
      setSelectedId(current => current ?? loadedResults.find(item => item.status === "AMBIGUOUS" || isAiEligibleResult(item))?.id ?? null);
    } catch (loadError) {
      if (loadError instanceof ApiClientError && loadError.status === 404) { setRun(null); setResults([]); return; }
      setError(errorMessage(loadError));
    }
  }, [investigationId]);

  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => { fetchProviderHealth().then(setProviderHealth).catch(() => setProviderHealth(null)); }, []);
  React.useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("result");
    if (requested && results.some(item => item.id === requested)) setSelectedId(requested);
  }, [results]);

  const selected = results.find(item => item.id === selectedId) ?? null;
  const exceptions = results.filter(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
  const attention = exceptions.filter(item => item.status === "AMBIGUOUS");
  const explained = exceptions.filter(item => item.status === "EXCEPTION" && !isAiEligibleResult(item));
  const findingCodes = Array.from(new Set(exceptions.flatMap(item => item.findings.map(finding => finding.code))));

  async function reconcile() {
    setWorking(true); setError(null);
    try {
      const dataset = await normalizeDataset(investigationId);
      const completed = await runInvestigationReconciliation(investigationId, dataset.id);
      const loadedResults = await fetchReconciliationResults(investigationId, completed.id);
      setRun(completed); setResults(loadedResults); setSelectedId(loadedResults.find(item => item.status === "AMBIGUOUS" || isAiEligibleResult(item))?.id ?? null); setInvestigation(null); setLifecycle(null); setReviewRequest(null);
    } catch (runError) { setError(errorMessage(runError)); } finally { setWorking(false); }
  }

  async function inspect(result: ApiReconciliationResult) {
    if (!run) return;
    setSelectedId(result.id); setInvestigation(null); setLifecycle(null); setReviewRequest(null); setError(null); setWorking(true);
    try {
      const [loadedInvestigation, loadedLifecycle] = await Promise.allSettled([fetchReconciliationInvestigation(investigationId, run.id, result.id), fetchInvestigationLifecycle(investigationId, result.order_id)]);
      if (loadedInvestigation.status === "fulfilled") setInvestigation(loadedInvestigation.value);
      if (loadedLifecycle.status === "fulfilled") setLifecycle(loadedLifecycle.value);
      const failed = [loadedInvestigation, loadedLifecycle].find(item => item.status === "rejected" && !(item.reason instanceof ApiClientError && item.reason.status === 404));
      if (failed?.status === "rejected") setError(errorMessage(failed.reason));
    } finally { setWorking(false); }
  }

  async function investigate() {
    if (!run || !selected || !isAiEligibleResult(selected)) return;
    setWorking(true); setError(null);
    try { setInvestigation(await investigateReconciliationResult(investigationId, run.id, selected.id)); }
    catch (investigateError) { setError(errorMessage(investigateError)); }
    finally { setWorking(false); }
  }

  async function requestDecision() {
    if (!run || !selected) return;
    setRequestingReview(true); setError(null);
    try { setReviewRequest(await requestFinancialResolution(investigationId, run.id, selected.id, reviewActionFor(selected.exception_type), requestId())); }
    catch (reviewError) { setError(errorMessage(reviewError)); }
    finally { setRequestingReview(false); }
  }

  async function decideReview(decision: "approve" | "reject") {
    if (!reviewRequest) return;
    setWorking(true); setError(null);
    try {
      const result = decision === "approve" ? await approveResolution(reviewRequest.request_id, requestId()) : await rejectResolution(reviewRequest.request_id, requestId());
      setReviewRequest(current => current ? { ...current, status: result.request_status, approvals_received: result.approvals_received } : current);
    } catch (decisionError) { setError(errorMessage(decisionError)); } finally { setWorking(false); }
  }

  const actor = currentActor();
  const canApprove = actor.role === "FINANCE_MANAGER" || actor.role === "CONTROLLER";
  const selectedState = selected ? closeStateForResult(selected, investigation) : null;
  const decisionRequired = Boolean(selected && investigation?.status !== "FAILED" && (selected.status === "AMBIGUOUS" || investigation?.status === "UNRESOLVED"));
  const sourceSummary = sourceCount === undefined ? "" : ` · ${sourceCount} source files`;
  return <Card id="reconciliation" className="mt-4"><CardHeader><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle>{investigationName ?? "Financial close"}</CardTitle><CardDescription>{periodStart && periodEnd ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}` : "Reconcile the period, then work only the items that need a decision."}{sourceSummary}</CardDescription></div>{run && <Button variant="outline" size="sm" onClick={() => document.getElementById("attention")?.scrollIntoView({ behavior: "smooth" })}>{attention.length > 0 ? "Review attention queue" : "Complete close"}</Button>}</div>{providerHealth && <details className="mt-3"><summary className="cursor-pointer text-[11px] font-semibold text-muted-foreground">Provider diagnostics</summary><ProviderHealthSummary health={providerHealth} /></details>}</CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{!run ? <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center"><div className="text-sm font-semibold text-foreground">Ready to close the period</div><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted-foreground">Normalize the confirmed source mappings into an immutable dataset, then run deterministic lifecycle checks.</p><Button className="mt-4" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? "Preparing close…" : "Normalize and reconcile"}</Button></div> : <><ReconciliationStory run={run} results={results} currency={currency} />{exceptions.length === 0 ? <Alert variant="info" className="mt-5"><AlertTitle>Close is clean</AlertTitle><AlertDescription>Every lifecycle reconciled without an exception or ambiguous association.</AlertDescription></Alert> : <><section className="mt-5 rounded-lg border border-border bg-card p-4"><div className="flex items-center justify-between gap-3"><div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Top findings</div><p className="mt-1 text-[11px] text-muted-foreground">Open a category to inspect its cases.</p></div><span className="text-[11px] text-muted-foreground">{exceptions.length} cases</span></div><div className="mt-3 grid gap-2 sm:grid-cols-2">{findingCodes.map(code => { const group = exceptions.filter(item => item.findings.some(finding => finding.code === code)); return <Button type="button" variant="outline" key={code} onClick={() => { const first = group[0]; if (first) void inspect(first); }} className="h-auto justify-between whitespace-normal p-3 text-left"><span className="text-xs font-semibold">{statusLabel(code)}</span><span className="text-[11px] text-muted-foreground">{group.length} case{group.length === 1 ? "" : "s"}</span></Button>; })}</div></section><section id="attention" className="mt-5 rounded-lg border border-warning/30 bg-warning/5 p-4"><div className="text-[10px] font-bold uppercase tracking-wide text-warning">Attention queue</div><p className="mt-1 text-[11px] text-muted-foreground">Ambiguity and optional cross-system evidence belong here. Deterministically explained findings stay out of this queue.</p>{attention.length === 0 ? <div className="mt-3 text-xs font-semibold text-foreground">Nothing needs attention.</div> : <div className="mt-3 space-y-2">{attention.map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className="w-full justify-between whitespace-normal rounded-md border border-warning/20 bg-card p-3 text-left"><span><span className="block text-xs font-semibold text-foreground">{item.order_id} · {statusLabel(item.exception_type ?? "AMBIGUOUS_ASSOCIATION")}</span><span className="mt-1 block text-[11px] text-muted-foreground">{item.status === "AMBIGUOUS" ? "Human decision required" : "Optional evidence investigation"}</span></span><StatusBadge status={item.status === "AMBIGUOUS" ? "NEEDS_HUMAN_DECISION" : "EXPLAINED"} /></Button>)}</div>}</section><details className="mt-5 rounded-lg border border-border p-4"><summary className="cursor-pointer text-xs font-semibold text-foreground">Explained findings · {explained.length}</summary><div className="mt-3 space-y-2">{explained.map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className="w-full justify-between whitespace-normal rounded-md border border-border p-3 text-left"><span><span className="block text-xs font-semibold text-foreground">{item.order_id} · {statusLabel(item.exception_type ?? "FINDING")}</span><span className="mt-1 block text-[11px] text-muted-foreground">Deterministic evidence is sufficient to explain this finding.</span></span><StatusBadge status="EXPLAINED" /></Button>)}</div></details><div className="mt-5 rounded-lg border border-border p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">What happened</div><div className="mt-1 text-sm font-semibold text-foreground">{selected ? statusLabel(selected.exception_type ?? "AMBIGUOUS_ASSOCIATION") : "Select a finding"}</div>{selected && <div className="mt-1 text-[11px] text-muted-foreground">{selected.order_id} · {selected.findings.map(item => item.code).join(", ")}</div>}{selected && <div className="mt-2"><StatusBadge status={selectedState ?? "EXPLAINED"} /></div>}</div>{selected && isAiEligibleResult(selected) ? <Button size="sm" onClick={() => void investigate()} disabled={working}>{working ? "Checking evidence…" : investigation ? "Re-run evidence check" : "Investigate evidence"}</Button> : selected ? <span className="text-[11px] font-semibold text-success">Explained from deterministic records</span> : null}</div>{lifecycle && selected && <LifecyclePreview lifecycle={lifecycle} exceptionType={selected.exception_type} />}{selected && !isAiEligibleResult(selected) && <div className="mt-4 rounded-md border border-success/20 bg-success/5 p-3 text-[11px] text-muted-foreground"><span className="font-semibold text-foreground">How do we know?</span> The deterministic findings are the explanation. No provider call is required.</div>}{investigation && <><InvestigationStory investigation={investigation} /><div className="mt-3 grid gap-3 sm:grid-cols-3"><MetricCell label="Root cause" value={investigation.root_cause_code ?? "Not established"} /><MetricCell label="Evidence score" value={`${investigation.evidence_score}/100`} /><MetricCell label="Verifier" value={investigation.verifier_passed ? "Passed" : "Failed"} /></div><EvidencePanel title="Supporting evidence" items={investigation.supporting_evidence} /><EvidencePanel title="Contradictory evidence" items={investigation.contradictory_evidence} />{investigation.rejected_evidence.length > 0 && <EvidencePanel title="Rejected evidence" items={investigation.rejected_evidence} />}</>}{selected && decisionRequired && (reviewRequest ? <div className="mt-4 rounded-md border border-info/30 bg-info/5 p-3"><div className="font-semibold text-foreground">Approval request · {statusLabel(reviewRequest.status)}</div><div className="mt-1 text-[11px] text-muted-foreground">Requested by {reviewRequest.requester_id} · {reviewRequest.approvals_received}/{reviewRequest.required_approvals} approvals · {statusLabel(reviewRequest.action_code)}</div>{reviewRequest.status === "PENDING_APPROVAL" && (canApprove && actor.id !== reviewRequest.requester_id ? <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={() => void decideReview("approve")} disabled={working}>Approve</Button><Button variant="outline" size="sm" onClick={() => void decideReview("reject")} disabled={working}>Reject</Button></div> : <p className="mt-3 text-[11px] text-muted-foreground">Waiting for a different authorized reviewer. The requester cannot approve their own request.</p>)}</div> : <Button variant="outline" className="mt-4" size="sm" onClick={() => void requestDecision()} disabled={working || requestingReview}>{requestingReview ? "Creating decision request…" : "Request controller decision"}</Button>)}</div></>}</>}</CardContent></Card>;
}

export function FinancialInvestigationSourcesPage({ investigationId }: { investigationId: string }) {
  const [investigation, setInvestigation] = React.useState<ApiFinancialInvestigation | null>(null);
  const [sources, setSources] = React.useState<ApiSourceFile[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState<string[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [generating, setGenerating] = React.useState(false);
  const [autoReviewSourceIds, setAutoReviewSourceIds] = React.useState<string[]>([]);
  const [demoForm, setDemoForm] = React.useState({ orders: 25, seed: 42, anomalyRatePercent: 30 });

  const load = React.useCallback(() => Promise.all([fetchFinancialInvestigation(investigationId), fetchSourceFiles(investigationId)]).then(([loadedInvestigation, loadedSources]) => { setInvestigation(loadedInvestigation); setSources(loadedSources); }).catch(loadError => setError(errorMessage(loadError))).finally(() => setLoading(false)), [investigationId]);
  React.useEffect(() => { void load(); }, [load]);

  async function handleFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length === 0) return;
    setError(null); setNotice(null);
    const invalid = files.find(file => !allowedExtensions.some(extension => file.name.toLowerCase().endsWith(extension)));
    if (invalid) { setError(`${invalid.name} is not supported. Upload CSV or XLSX files only.`); return; }
    setUploading(files.map(file => file.name));
    const analyzedFiles: string[] = [];
    const deduplicatedFiles: string[] = [];
    for (const file of files) {
      try {
        const uploaded = await uploadSourceFile(investigationId, file, requestId());
        setSources(current => current.some(item => item.id === uploaded.id) ? current : [...current, uploaded]);
        if (uploaded.deduplicated) {
          deduplicatedFiles.push(file.name);
          continue;
        }
        const analysis = await analyzeSourceFile(investigationId, uploaded.id);
        setSources(current => current.map(item => item.id === uploaded.id ? { ...item, status: "MAPPING_REQUIRED", detected_source_type: analysis.source_type, detection_confidence: analysis.classification_confidence } : item));
        setAutoReviewSourceIds(current => [...current, uploaded.id]);
        analyzedFiles.push(file.name);
      }
      catch (uploadError) { setError(`${file.name}: ${errorMessage(uploadError)}`); }
      finally { setUploading(current => current.filter(name => name !== file.name)); }
    }
    await load();
    const messages = [];
    if (analyzedFiles.length > 0) messages.push(`Uploaded and analyzed ${analyzedFiles.length} source file${analyzedFiles.length === 1 ? "" : "s"}. High-confidence mappings are confirmed automatically; only uncertain sources need review.`);
    if (deduplicatedFiles.length > 0) messages.push(`${deduplicatedFiles.length} file${deduplicatedFiles.length === 1 ? " was" : "s were"} already attached, so no duplicate was created.`);
    setNotice(messages.length > 0 ? messages.join(" ") : "No source files were analyzed.");
  }

  async function handleDemoGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sources.length > 0) return;
    setGenerating(true); setError(null); setNotice(null);
    const payload: DemoDataRequest = { orders: demoForm.orders, seed: demoForm.seed, anomaly_rate: demoForm.anomalyRatePercent / 100 };
    try {
      const result = await generateDemoData(investigationId, payload, requestId());
      setSources(result.sources);
      setNotice(`Generated ${result.orders.toLocaleString()} synthetic orders and attached ${result.sources.length} source files. Continue with source analysis and mapping review.`);
    } catch (generationError) { setError(errorMessage(generationError)); }
    finally { setGenerating(false); }
  }

  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation…</div>;
  if (!investigation) return <Alert variant="destructive"><AlertTitle>Investigation not found</AlertTitle><AlertDescription>{error ?? "This investigation is not available in the current workspace."}</AlertDescription></Alert>;
  return <>
    <div className="mb-5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Link href="/investigations" className="flex items-center gap-1 font-semibold hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Investigations</Link><span>/</span><span>{investigation.id}</span></div>
    <InvestigationStageNav investigationId={investigation.id} /><PageHeading eyebrow="Source intake" title={investigation.name} description="Upload trusted exports for this investigation. FinTrace validates file structure at the API boundary before any mapping or analysis begins."><Button asChild variant="outline" size="sm"><Link href={`/investigations/${investigation.id}`}>Overview</Link></Button></PageHeading>
    {error && <Alert variant="destructive" className="mb-4"><AlertTitle>Source intake needs attention</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {notice && <Alert variant="info" className="mb-4"><CheckCircle2 className="mr-2 inline h-4 w-4" />{notice}</Alert>}
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]"><div className="grid gap-4"><Card><CardHeader><CardTitle>Upload source files</CardTitle><CardDescription>Supported formats: CSV and XLSX. Every file is analyzed automatically after upload; you only confirm the proposed mappings.</CardDescription></CardHeader><CardContent><label htmlFor="source-upload" className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 px-6 py-12 text-center transition-colors hover:border-primary/50 hover:bg-muted/50"><UploadCloud className="h-8 w-8 text-primary" /><span className="mt-3 text-sm font-semibold text-foreground">Choose source exports</span><span className="mt-1 text-xs text-muted-foreground">Select multiple CSV or XLSX files. Upload, analysis, and mapping proposals run in sequence.</span><span className="mt-4 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground">Browse files</span><FileInput id="source-upload" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple onChange={handleFiles} /></label>{uploading.length > 0 && <div className="mt-4 space-y-2" role="status">{uploading.map(name => <div key={name} className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Uploading and analyzing {name}…</div>)}</div>}</CardContent></Card><Card><CardHeader><CardTitle>Generate fresh synthetic data</CardTitle><CardDescription>Use the same upload boundary with reproducible, generated CSV sources. No fixture snapshot is substituted.</CardDescription></CardHeader><CardContent><form onSubmit={handleDemoGenerate} className="space-y-4"><div><label htmlFor="demo-orders" className="text-xs font-semibold text-foreground">Orders</label><Input id="demo-orders" type="number" min={1} max={2000} className="mt-2" value={demoForm.orders} onChange={event => setDemoForm({ ...demoForm, orders: Number(event.target.value) || 1 })} /></div><div className="grid gap-3 sm:grid-cols-2"><div><label htmlFor="demo-seed" className="text-xs font-semibold text-foreground">Seed</label><Input id="demo-seed" type="number" min={0} max={2147483647} className="mt-2" value={demoForm.seed} onChange={event => setDemoForm({ ...demoForm, seed: Number(event.target.value) || 0 })} /></div><div><label htmlFor="demo-anomaly-rate" className="text-xs font-semibold text-foreground">Anomaly rate %</label><Input id="demo-anomaly-rate" type="number" min={0} max={100} step={1} className="mt-2" value={demoForm.anomalyRatePercent} onChange={event => setDemoForm({ ...demoForm, anomalyRatePercent: Number(event.target.value) || 0 })} /></div></div>{sources.length > 0 && <p className="text-[11px] leading-5 text-muted-foreground">Fresh generation is available only before sources are attached. Remove the current set if you want to generate a different one.</p>}<Button type="submit" size="sm" disabled={generating || sources.length > 0}><Sparkles className="h-3.5 w-3.5" />{generating ? "Generating…" : "Generate and attach"}</Button></form></CardContent></Card></div><Card><CardHeader><CardTitle>Ingestion safeguards</CardTitle></CardHeader><CardContent className="space-y-4 text-xs"><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Files are scoped to <strong className="text-foreground">{investigation.organization_id}</strong> and linked to this investigation.</p></div><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Only bounded structural metadata is used for the next mapping step. Raw files are not sent to an AI provider.</p></div><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Uploaded content is untrusted input and cannot change financial state by itself.</p></div></CardContent></Card></div>
    <Card className="mt-4"><CardHeader><CardTitle>Attached sources <span className="ml-1 text-muted-foreground">({sources.length})</span></CardTitle><CardDescription>Sources are analyzed automatically. High-confidence mappings are confirmed automatically; only uncertain sources need review.</CardDescription></CardHeader><CardContent>{sources.length === 0 ? <div className="py-8 text-center text-sm text-muted-foreground">No source files attached yet.</div> : sources.map(source => <SourceFileRow key={source.id} investigationId={investigation.id} source={source} autoReview={autoReviewSourceIds.includes(source.id)} onDeleted={sourceId => setSources(current => current.filter(item => item.id !== sourceId))} onChanged={updated => setSources(current => current.map(item => item.id === updated.id ? updated : item))} />)}</CardContent></Card>
  </>;
}

export function FinancialInvestigationDetailPage({ investigationId }: { investigationId: string }) {
  const [investigation, setInvestigation] = React.useState<ApiFinancialInvestigation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchFinancialInvestigation(investigationId).then(setInvestigation).catch(loadError => setError(errorMessage(loadError))).finally(() => setLoading(false)); }, [investigationId]);
  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation…</div>;
  if (!investigation) return <Alert variant="destructive"><AlertTitle>Investigation not found</AlertTitle><AlertDescription>{error ?? "This investigation is not available in the current workspace."}</AlertDescription></Alert>;
  return <><div className="mb-5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Link href="/investigations" className="flex items-center gap-1 font-semibold hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Investigations</Link><span>/</span><span>{investigation.name}</span></div><PageHeading eyebrow="Month-end close" title={investigation.name} description="Follow the close from source understanding to a reconciled, explainable, auditable result."><StatusBadge status={investigation.status} /></PageHeading><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Close status</div><div className="mt-2"><StatusBadge status={investigation.status} /></div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Sources</div><div className="mt-2 text-xl font-bold text-foreground">{investigation.source_file_count}</div><div className="text-xs text-muted-foreground">Files in this close</div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Period</div><div className="mt-2 text-sm font-semibold text-foreground">{formatDate(investigation.period_start)}</div><div className="text-xs text-muted-foreground">to {formatDate(investigation.period_end)}</div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Currency</div><div className="mt-2 text-xl font-bold text-foreground">{investigation.base_currency}</div><div className="text-xs text-muted-foreground">Rules remain deterministic</div></CardContent></Card></div><RelationshipReview investigationId={investigation.id} /><ReconciliationRunPanel investigationId={investigation.id} currency={investigation.base_currency} investigationName={investigation.name} periodStart={investigation.period_start} periodEnd={investigation.period_end} sourceCount={investigation.source_file_count} /><Card className="mt-4"><CardHeader><CardTitle>Close stages</CardTitle><CardDescription>Each stage has one job. Return to Sources or Relationships only when setup needs attention.</CardDescription></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-4">{["Understand sources", "Confirm uncertain mappings", "Review uncertain relationships", "Reconcile and close"].map((step, index) => <div key={step} className="rounded-lg border border-border p-4"><div className="flex items-center gap-2 text-xs font-semibold text-foreground"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">{index + 1}</span>{step}</div><p className="mt-2 text-[11px] leading-5 text-muted-foreground">{index === 0 ? "Attach and validate CSV/XLSX exports." : index === 1 ? "Only incomplete or uncertain fields need review." : index === 2 ? "Accept safe links and decide on duplicate or conflicting evidence." : "Build the immutable dataset and reconcile the period."}</p></div>)}</div><Button asChild className="mt-5" size="sm"><Link href={`/investigations/${investigation.id}/sources`}>Open source setup <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card></>;
}
