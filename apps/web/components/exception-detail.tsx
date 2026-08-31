"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, FileText, Info, LockKeyhole, MoreHorizontal, Play, ShieldCheck, Sparkles, UserRound, X } from "lucide-react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Progress, cn } from "@fintrace/ui";
import { ApiClientError, fetchAuditEvents, fetchException, fetchExceptionGraph, fetchLifecycle, requestResolution, startInvestigation } from "../lib/api-client";
import { downloadCsv } from "../lib/export";
import { appConfig, formatCurrency } from "../lib/data";
import type { ApiAuditEvent, ApiExceptionSummary, ApiInvestigation, ApiLifecycleGraph, ApiLifecycleResponse, ExceptionType, Investigation, LifecycleRecord, ResolutionActionCode, TimelineEvent } from "../lib/types";
import { SeverityBadge, StatusBadge } from "./status-badge";

const reviewActionByType: Partial<Record<ExceptionType, ResolutionActionCode>> = {
  REFUND_WITHOUT_INVENTORY_RETURN: "REQUEST_INVENTORY_VERIFICATION",
  REFUND_WITHOUT_ERP_REVERSAL: "REQUEST_ERP_INVOICE_CORRECTION",
  MISSING_SETTLEMENT: "REQUEST_SETTLEMENT_REVIEW",
  SETTLEMENT_TIMING: "MARK_AS_TIMING_DIFFERENCE",
  SETTLEMENT_FEE_VARIANCE: "MARK_AS_EXPECTED_FEE_VARIANCE",
  ERP_INVOICE_MISSING: "REQUEST_ERP_INVOICE_CORRECTION",
  ERP_AMOUNT_MISMATCH: "REQUEST_ERP_INVOICE_CORRECTION",
  DUPLICATE_PAYMENT: "REQUEST_PAYMENT_REVIEW",
  AMBIGUOUS_ASSOCIATION: "REQUEST_PAYMENT_REVIEW",
  MANUAL_WORKFLOW_ANOMALY: "ESCALATE_TO_FINANCE_MANAGER"
};

const lifecycleStyles: Record<LifecycleRecord["status"], { icon: React.ReactNode; marker: string; surface: string }> = {
  confirmed: { icon: <Check className="h-3 w-3" />, marker: "bg-success/10 text-success", surface: "border-border bg-muted/30" },
  missing: { icon: <X className="h-3 w-3" />, marker: "bg-destructive/10 text-destructive", surface: "border-destructive/20 bg-destructive/5" },
  warning: { icon: <Info className="h-3 w-3" />, marker: "bg-warning/15 text-warning-foreground", surface: "border-warning/30 bg-warning/5" }
};

export function ExceptionDetail({ id }: { id: string }) {
  const [exception, setException] = React.useState<ApiExceptionSummary | null>(null);
  const [lifecycle, setLifecycle] = React.useState<ApiLifecycleResponse | null>(null);
  const [auditEvents, setAuditEvents] = React.useState<ApiAuditEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<Investigation | null>(null);
  const [investigating, setInvestigating] = React.useState(false);
  const [investigationError, setInvestigationError] = React.useState<string | null>(null);
  const [requested, setRequested] = React.useState(false);
  const [requesting, setRequesting] = React.useState(false);
  const [requestError, setRequestError] = React.useState<string | null>(null);
  const [moreOpen, setMoreOpen] = React.useState(false);
  const [graphVisible, setGraphVisible] = React.useState(false);
  const [graphLoading, setGraphLoading] = React.useState(false);
  const [graphError, setGraphError] = React.useState<string | null>(null);
  const [graph, setGraph] = React.useState<ApiLifecycleGraph | null>(null);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(null);
    (async () => {
      try {
        const loadedException = await fetchException(id);
        const [loadedLifecycle, loadedAudit] = await Promise.all([fetchLifecycle(loadedException.order_id), fetchAuditEvents(loadedException.id)]);
        if (!active) return;
        setException(loadedException);
        setLifecycle(loadedLifecycle);
        setAuditEvents(loadedAudit);
      } catch {
        if (active) setLoadError("This exception could not be loaded from the organization-scoped API.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [id]);

  async function investigate() {
    if (!exception) return;
    setInvestigating(true); setInvestigationError(null);
    try { setInvestigation(mapApiInvestigation(await startInvestigation(id, `investigation-${id}`))); }
    catch (error) { setInvestigationError(error instanceof ApiClientError && error.status === 503 ? "AI provider unavailable. Deterministic evidence remains available for manual review." : "The investigation service is unavailable. Deterministic evidence remains available for manual review."); }
    finally { setInvestigating(false); }
  }

  async function requestReview() {
    if (!exception) return;
    setRequesting(true); setRequestError(null);
    try {
      await requestResolution(id, reviewActionByType[exception.type] ?? "REQUEST_REFUND_REVIEW", `review-${id}-${Date.now()}`);
      setRequested(true);
    } catch { setRequestError("The review request could not be recorded. Check that the API is available and try again."); }
    finally { setRequesting(false); }
  }

  async function viewGraph() {
    if (graph) { setGraphVisible(value => !value); return; }
    setGraphLoading(true); setGraphError(null);
    try { setGraph(await fetchExceptionGraph(id)); setGraphVisible(true); }
    catch { setGraphError("The lifecycle graph could not be loaded. The canonical lifecycle remains available below."); }
    finally { setGraphLoading(false); }
  }

  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><span className="h-2 w-2 animate-pulse rounded-full bg-info" />Loading organization-scoped exception evidence…</div>;
  if (loadError || !exception || !lifecycle) return <><PageBack /><Alert variant="destructive" className="max-w-2xl">{loadError ?? "This exception is not available."}</Alert></>;

  const records = buildLifecycleRecords(exception, lifecycle);
  const timeline = buildTimeline(exception, lifecycle, records);
  const loadedException = exception;
  const reviewStatus = requested ? "IN_REVIEW" : loadedException.status;
  function copyExceptionId() { navigator.clipboard?.writeText(loadedException.id).then(() => setMoreOpen(false)).catch(() => undefined); }
  function exportEvidence() {
    downloadCsv(`fintrace-${loadedException.id}-evidence.csv`, ["Source", "Record ID", "Fact"], records.map(item => [item.source, item.id === "—" ? "" : item.id, item.detail]));
    setMoreOpen(false);
  }

  return <>
    <PageBack id={exception.id} />
    {requestError && <Alert variant="destructive" className="mb-4 text-xs">{requestError}</Alert>}
    <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-start"><div><div className="mb-2 flex flex-wrap items-center gap-2"><span className="font-mono text-[11px] font-semibold text-muted-foreground">{exception.id}</span><SeverityBadge severity={exception.severity} /><StatusBadge status={reviewStatus} /></div><h1 className="text-[26px] font-bold tracking-[-0.03em] text-foreground">{labelForException(exception.type)}</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">{exception.rules_triggered.length} deterministic rule{exception.rules_triggered.length === 1 ? "" : "s"} triggered: {exception.rules_triggered.join(", ") || "No rule details recorded"}.</p></div><div className="relative flex items-center gap-2"><Button variant="outline" size="sm" onClick={() => setMoreOpen(value => !value)} aria-expanded={moreOpen}><MoreHorizontal className="h-3.5 w-3.5" />More</Button>{moreOpen && <div role="menu" className="absolute right-0 top-10 z-10 w-48 rounded-lg border border-border bg-card p-1 shadow-lg"><Button variant="ghost" size="sm" className="w-full justify-start" onClick={copyExceptionId}>Copy exception ID</Button><Button variant="ghost" size="sm" className="w-full justify-start" onClick={exportEvidence}>Export evidence</Button><Button asChild variant="ghost" size="sm" className="w-full justify-start"><Link href="/patterns">Review patterns</Link></Button></div>}<Button size="sm" onClick={requestReview} disabled={requested || requesting}>{requesting ? <><Play className="h-3.5 w-3.5 animate-pulse" />Requesting…</> : requested ? <><Check className="h-3.5 w-3.5" />Review requested</> : <><Play className="h-3.5 w-3.5" />Request review</>}</Button></div></div>
    <div className="mb-5 grid gap-4 sm:grid-cols-3"><SummaryCard label="Financial exposure" value={formatCurrency(Number(exception.financial_exposure), exception.currency)} detail="Requires controlled review" tone="destructive" /><SummaryCard label="Lifecycle" value={exception.order_id} detail={`${exception.rules_triggered.length} deterministic rules triggered`} /><SummaryCard label="Policy owner" value={policyFor(exception.severity).owner} detail={policyFor(exception.severity).state} /></div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]"><div className="space-y-5"><LifecycleCard records={records} graphVisible={graphVisible} graphLoading={graphLoading} graphError={graphError} graph={graph} onViewGraph={viewGraph} /><TimelineCard events={timeline} /><AuditCard events={auditEvents} /></div><div className="space-y-5"><Card className="border-border"><CardHeader className="border-b border-border bg-muted/30"><div className="flex items-center gap-2"><div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10 text-accent"><Sparkles className="h-4 w-4" /></div><div><CardTitle>Evidence investigation</CardTitle><p className="mt-1 text-xs text-muted-foreground">Bounded, read-only AI analysis</p></div></div></CardHeader><CardContent className="p-5">{investigationError && <Alert variant="destructive" className="mb-4">{investigationError}</Alert>}{!investigation ? <div><div className="rounded-lg border border-accent/20 bg-accent/5 p-4"><div className="flex gap-3"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-accent" /><p className="text-xs leading-5 text-muted-foreground">FinTrace will inspect only relevant, organization-scoped evidence using approved read-only tools. No financial action will be taken.</p></div></div><Button className="mt-4 w-full" onClick={investigate} disabled={investigating}><Sparkles className="h-3.5 w-3.5" />{investigating ? "Investigating…" : "Investigate exception"}</Button><div className="mt-3 text-center text-[10px] text-muted-foreground">Deterministic evidence remains visible while investigation runs.</div></div> : <InvestigationResult investigation={investigation} />}</CardContent></Card><PolicyCard exception={exception} /><RelatedAnalysis /></div></div>
  </>;
}

function PageBack({ id }: { id?: string }) { return <div className="mb-5 flex items-center gap-2 text-xs text-muted-foreground"><Link href="/exceptions" className="flex items-center gap-1 font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Exceptions</Link>{id && <><span>/</span><span>{id}</span></>}</div>; }

function labelForException(type: ExceptionType) { return type.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, value => value.toUpperCase()); }
function policyFor(severity: string) { return severity === "CRITICAL" || severity === "HIGH" ? { owner: "Controller", state: "Approval required", reason: "High exposure or financial reversal" } : { owner: "Finance Manager", state: "Approval required", reason: "Controlled financial action" }; }
function textValue(value: unknown) { return value === null || value === undefined || value === "" ? null : String(value); }
function amountValue(record: Record<string, unknown>) { const amount = record.amount_minor ?? record.gross_minor ?? record.net_minor; return amount === null || amount === undefined ? undefined : formatCurrency(Number(amount) / 100); }
function recordTime(record: Record<string, unknown>) { return ["created_at", "captured_at", "settled_at", "processed_at", "occurred_at"].map(key => textValue(record[key])).find(Boolean) ?? null; }
function lifecycleRows(lifecycle: ApiLifecycleResponse, key: "order" | "payments" | "settlements" | "invoices" | "refunds" | "inventory_movements" | "employee_actions") { const value = lifecycle[key]; return Array.isArray(value) ? value : [value]; }

function buildLifecycleRecords(exception: ApiExceptionSummary, lifecycle: ApiLifecycleResponse): LifecycleRecord[] {
  const definitions: { key: "order" | "payments" | "settlements" | "invoices" | "refunds" | "inventory_movements" | "employee_actions"; source: string; idKey: string }[] = [
    { key: "order", source: "Order", idKey: "order_id" }, { key: "payments", source: "Payment", idKey: "payment_id" }, { key: "settlements", source: "Settlement", idKey: "settlement_id" }, { key: "invoices", source: "Invoice", idKey: "invoice_id" }, { key: "refunds", source: "Refund", idKey: "refund_id" }, { key: "inventory_movements", source: "Inventory movement", idKey: "movement_id" }, { key: "employee_actions", source: "Employee action", idKey: "action_id" }
  ];
  const records: LifecycleRecord[] = [];
  for (const definition of definitions) {
    for (const row of lifecycleRows(lifecycle, definition.key)) {
      if (!row || typeof row !== "object") continue;
      const record = row as Record<string, unknown>;
      const id = textValue(record[definition.idKey]);
      if (!id) continue;
      const warning = (exception.type === "SETTLEMENT_TIMING" || exception.type === "SETTLEMENT_FEE_VARIANCE") && definition.key === "settlements";
      records.push({ id, source: definition.source, status: warning ? "warning" : "confirmed", amount: amountValue(record), detail: textValue(record.status) ?? textValue(record.action) ?? "Observed in canonical lifecycle" });
    }
  }
  const missing: { source: string; detail: string }[] = [];
  if (exception.type === "MISSING_SETTLEMENT" && lifecycle.settlements.length === 0) missing.push({ source: "Settlement", detail: "Expected settlement was not observed" });
  if (exception.type === "ERP_INVOICE_MISSING" && lifecycle.invoices.length === 0) missing.push({ source: "Invoice", detail: "Expected invoice was not observed" });
  if (exception.type === "REFUND_WITHOUT_INVENTORY_RETURN" && lifecycle.refunds.length > 0 && !lifecycle.inventory_movements.some(item => item.movement_type === "RETURN")) missing.push({ source: "Inventory return", detail: "Expected RETURN movement was not observed" });
  if ((exception.type === "REFUND_WITHOUT_ERP_REVERSAL" || exception.rules_triggered.includes("ERP_REVERSAL_MISSING")) && lifecycle.invoices.length > 0) missing.push({ source: "ERP reversal", detail: "Expected reversal was not observed" });
  return [...records, ...missing.map(item => ({ id: "—", source: item.source, status: "missing" as const, detail: item.detail }))];
}

function buildTimeline(exception: ApiExceptionSummary, lifecycle: ApiLifecycleResponse, records: LifecycleRecord[]): TimelineEvent[] {
  const sourceDefinitions: Record<string, { key: "order" | "payments" | "settlements" | "invoices" | "refunds" | "inventory_movements" | "employee_actions"; idKey: string }> = {
    Order: { key: "order", idKey: "order_id" }, Payment: { key: "payments", idKey: "payment_id" }, Settlement: { key: "settlements", idKey: "settlement_id" }, Invoice: { key: "invoices", idKey: "invoice_id" }, Refund: { key: "refunds", idKey: "refund_id" }, "Inventory movement": { key: "inventory_movements", idKey: "movement_id" }, "Employee action": { key: "employee_actions", idKey: "action_id" }
  };
  const entries = records.map(record => {
    const definition = sourceDefinitions[record.source];
    const row = definition ? lifecycleRows(lifecycle, definition.key).find(item => item && typeof item === "object" && String(item[definition.idKey]) === record.id) : undefined;
    const timestamp = row && typeof row === "object" ? recordTime(row as Record<string, unknown>) : null;
    return { time: timestamp ? new Date(timestamp).toLocaleString() : "—", title: record.status === "missing" ? `${record.source} expected` : `${record.source} observed`, detail: record.id === "—" ? record.detail : `${record.id}${record.amount ? ` · ${record.amount}` : ""}`, source: record.source, state: record.status === "confirmed" ? "complete" as const : record.status };
  });
  entries.push({ time: new Date(exception.detected_at).toLocaleString(), title: "Exception recorded", detail: exception.type, source: "FinTrace rule engine", state: "missing" });
  return entries.sort((a, b) => a.time === "—" ? 1 : b.time === "—" ? -1 : a.time.localeCompare(b.time));
}

function mapApiInvestigation(item: ApiInvestigation): Investigation { return { status: item.status, rootCause: item.root_cause_code ?? "Unresolved", rootCauseCode: item.root_cause_code ?? "UNKNOWN", summary: item.summary, evidenceScore: item.evidence_score, supportingEvidence: item.supporting_evidence.map(evidence => ({ ...evidence, tone: "positive" as const })), contradictoryEvidence: item.contradictory_evidence.map(evidence => ({ ...evidence, tone: "warning" as const })), missingEvidence: item.missing_evidence, action: item.recommended_action_code ?? "Manual review", actionCode: item.recommended_action_code ?? "REQUEST_MANUAL_REVIEW", requiresHumanReview: item.requires_human_review, tools: item.tool_calls.map(call => ({ name: call.name, target: call.target, duration: `${call.duration_ms}ms` })) }; }

function SummaryCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: "destructive" }) { return <Card><CardContent className="p-4"><div className="text-[11px] font-medium text-muted-foreground">{label}</div><div className="mt-2 text-xl font-bold tracking-tight text-foreground">{value}</div><div className={cn("mt-1 text-[11px]", tone === "destructive" ? "text-destructive" : "text-muted-foreground")}>{detail}</div></CardContent></Card>; }

function LifecycleCard({ records, graphVisible, graphLoading, graphError, graph, onViewGraph }: { records: LifecycleRecord[]; graphVisible: boolean; graphLoading: boolean; graphError: string | null; graph: ApiLifecycleGraph | null; onViewGraph: () => void }) { return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Transaction lifecycle</CardTitle><p className="mt-1 text-xs text-muted-foreground">Canonical records returned by the organization-scoped lifecycle API</p></div><Button variant="link" size="sm" onClick={onViewGraph} disabled={graphLoading}>{graphLoading ? "Loading graph…" : graphVisible ? "Hide graph" : "View graph"} <ArrowRight className="h-3.5 w-3.5" /></Button></CardHeader><CardContent><div className="grid gap-2 sm:grid-cols-2">{records.map((record, index) => { const style = lifecycleStyles[record.status]; return <div key={`${record.source}-${record.id}-${index}`} className={cn("rounded-lg border p-3", style.surface)}><div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><span className={cn("flex h-5 w-5 items-center justify-center rounded-full", style.marker)}>{style.icon}</span><span className="text-xs font-semibold text-foreground">{record.source}</span></div><span className="font-mono text-[10px] text-muted-foreground">{record.id}</span></div>{record.amount && <div className="mt-3 text-sm font-bold text-foreground">{record.amount}</div>}<div className="mt-1 text-[11px] text-muted-foreground">{record.detail}</div></div>; })}</div>{graphError && <Alert variant="warning" className="mt-4 text-xs">{graphError}</Alert>}{graphVisible && graph && <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4"><div className="mb-3 flex items-center justify-between"><div className="text-xs font-semibold text-foreground">Derived event graph</div><div className="text-[10px] text-muted-foreground">{graph.nodes.length} nodes · {graph.edges.length} links</div></div><div className="grid gap-2 sm:grid-cols-2">{graph.nodes.map(node => <div key={node.id} className={cn("rounded-md border px-3 py-2", node.state === "MISSING" ? "border-destructive/30 bg-destructive/5" : "border-border bg-card")}><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-foreground">{node.label}</span><span className={cn("font-mono text-[9px]", node.state === "MISSING" ? "text-destructive" : "text-muted-foreground")}>{node.state}</span></div><div className="mt-1 font-mono text-[10px] text-muted-foreground">{node.id}</div></div>)}</div><div className="mt-3 space-y-1 border-t border-border pt-3">{graph.edges.map(edge => <div key={`${edge.source}-${edge.target}-${edge.relationship}`} className="font-mono text-[9px] text-muted-foreground">{edge.source} → {edge.target} · {edge.relationship}</div>)}</div></div>}</CardContent></Card>; }

function TimelineCard({ events }: { events: TimelineEvent[] }) { return <Card><CardHeader><CardTitle>Incident timeline</CardTitle><p className="mt-1 text-xs text-muted-foreground">Derived from canonical timestamps and the exception event</p></CardHeader><CardContent>{events.length === 0 ? <p className="text-xs text-muted-foreground">No timestamped lifecycle events are available.</p> : <div className="relative ml-2 border-l border-border pl-6">{events.map((event, index) => <div key={`${event.time}-${event.title}-${index}`} className="relative pb-6 last:pb-0"><span className={cn("absolute -left-[31px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-card", event.state === "complete" ? "bg-success" : event.state === "warning" ? "bg-warning" : "bg-destructive")}>{event.state === "complete" && <Check className="h-2.5 w-2.5 text-success-foreground" />}</span><div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-xs font-semibold text-foreground">{event.title}</div><div className="mt-1 text-[11px] text-muted-foreground">{event.detail}</div></div><div className="flex items-center gap-2 text-[10px] text-muted-foreground"><span>{event.source}</span><span className="font-mono">{event.time}</span></div></div></div>)}</div>}</CardContent></Card>; }

function AuditCard({ events }: { events: ApiAuditEvent[] }) { return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Audit history</CardTitle><p className="mt-1 text-xs text-muted-foreground">Append-only events returned for this exception resource</p></div><ShieldCheck className="h-4 w-4 text-success" /></CardHeader><CardContent className="p-0">{events.length === 0 ? <p className="px-5 py-6 text-xs text-muted-foreground">No audit events are currently associated with this exception.</p> : <div className="divide-y divide-border">{events.map(event => <div key={event.event_id} className="flex items-center gap-3 px-5 py-3.5"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted"><FileText className="h-3.5 w-3.5 text-muted-foreground" /></div><div className="min-w-0 flex-1"><div className="text-xs font-semibold text-foreground">{event.action}</div><div className="mt-0.5 truncate text-[11px] text-muted-foreground">{event.actor_id} · {event.correlation_id}</div></div><span className="font-mono text-[10px] text-muted-foreground">{new Date(event.created_at).toLocaleTimeString()}</span></div>)}</div>}</CardContent></Card>; }

function PolicyCard({ exception }: { exception: ApiExceptionSummary }) { const policy = policyFor(exception.severity); return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Approval guardrail</CardTitle><p className="mt-1 text-xs text-muted-foreground">Why this incident cannot auto-resolve</p></div><LockKeyhole className="h-4 w-4 text-muted-foreground" /></CardHeader><CardContent><div className="flex items-start gap-3"><div className="mt-0.5 h-2 w-2 rounded-full bg-warning" /><div><div className="text-xs font-semibold text-foreground">{policy.state}</div><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{policy.reason}. The requested action is subject to a {policy.owner.toLowerCase()} decision.</p></div></div><div className="mt-4 flex items-center gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground"><UserRound className="h-3.5 w-3.5" />Current actor: {appConfig.actor.name} · {appConfig.actor.role}</div></CardContent></Card>; }
function RelatedAnalysis() { return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Related analysis</CardTitle><p className="mt-1 text-xs text-muted-foreground">Use investigation-scoped patterns for recurring signals.</p></div><Badge variant="muted">Advisory</Badge></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">Cross-exception similarity is not asserted by this resource. Open Patterns after running a financial investigation to review deterministic recurring signals.</p><Button asChild variant="link" className="mt-3 w-full justify-between border-t border-border pt-3"><Link href="/patterns">Open patterns <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card>; }

function InvestigationResult({ investigation }: { investigation: Investigation }) { const failed = investigation.status === "FAILED"; const unresolved = investigation.status === "UNRESOLVED"; return <div><div className="flex items-center justify-between"><div className="flex items-center gap-2"><span className={cn("flex h-6 w-6 items-center justify-center rounded-full", failed ? "bg-destructive/10 text-destructive" : unresolved ? "bg-warning/10 text-warning" : "bg-success/10 text-success")}>{failed ? <X className="h-3.5 w-3.5" /> : unresolved ? <Info className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}</span><span className={cn("text-xs font-bold", failed ? "text-destructive" : unresolved ? "text-warning" : "text-success")}>{investigation.status}</span></div><span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{failed ? "Provider unavailable" : unresolved ? "Needs human review" : "Verified result"}</span></div><div className="mt-4 text-sm font-bold text-foreground">{investigation.rootCause}</div><p className="mt-2 text-xs leading-5 text-muted-foreground">{investigation.summary}</p><div className="mt-5 rounded-lg border border-border p-3"><div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-muted-foreground">Evidence score</span><span className="text-sm font-bold text-foreground">{investigation.evidenceScore}<span className="text-[11px] font-medium text-muted-foreground">/100</span></span></div><Progress value={investigation.evidenceScore} className="mt-2" /><div className="mt-2 text-[10px] text-muted-foreground">Evidence strength · not an AI confidence score</div></div><div className="mt-5"><div className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Supporting evidence</div><div className="space-y-2">{investigation.supportingEvidence.map(item => <div key={`${item.source}-${item.fact}`} className="flex gap-2 text-[11px] leading-4"><span className={cn("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", item.tone === "positive" ? "bg-success" : item.tone === "warning" ? "bg-destructive" : "bg-muted-foreground")} /><span className="text-muted-foreground"><strong className="font-semibold text-foreground">{item.source}:</strong> {item.fact}</span></div>)}</div></div><div className="mt-5 rounded-lg bg-info/10 p-3"><div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-info"><ArrowRight className="h-3.5 w-3.5" />Recommended next action</div><div className="mt-1.5 text-xs font-semibold text-info">{investigation.action}</div><div className="mt-2 text-[10px] leading-4 text-info">Human review required. No resolution performed.</div></div><div className="mt-5 border-t border-border pt-4"><div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground"><span>Read-only tool calls</span><span>{investigation.tools.length} tools</span></div><div className="space-y-1.5">{investigation.tools.map(tool => <div key={tool.name} className="flex items-center justify-between rounded bg-muted px-2.5 py-2 font-mono text-[10px]"><span className="text-muted-foreground">{tool.name}<span className="text-muted-foreground">({tool.target})</span></span><span className="text-muted-foreground">{tool.duration}</span></div>)}</div></div></div>; }
