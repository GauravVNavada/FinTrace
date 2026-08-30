"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, FileText, Info, LockKeyhole, MoreHorizontal, Play, ShieldCheck, Sparkles, UserRound, X } from "lucide-react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Progress, cn } from "@fintrace/ui";
import { fetchException, fetchExceptionGraph, requestResolution, startInvestigation } from "../lib/api-client";
import { downloadCsv } from "../lib/export";
import { appConfig, exceptionDetails, formatCurrency } from "../lib/data";
import type { ApiExceptionSummary, ApiInvestigation, ExceptionDetail as ExceptionDetailType, Investigation, LifecycleRecord, ResolutionActionCode } from "../lib/types";
import { SeverityBadge, StatusBadge } from "./status-badge";

const lifecycleStyles: Record<LifecycleRecord["status"], { icon: React.ReactNode; marker: string; surface: string }> = {
  confirmed: { icon: <Check className="h-3 w-3" />, marker: "bg-success/10 text-success", surface: "border-border bg-muted/30" },
  missing: { icon: <X className="h-3 w-3" />, marker: "bg-destructive/10 text-destructive", surface: "border-destructive/20 bg-destructive/5" },
  warning: { icon: <Info className="h-3 w-3" />, marker: "bg-warning/15 text-warning-foreground", surface: "border-warning/30 bg-warning/5" }
};

const reviewActionByType: Partial<Record<ExceptionDetailType["type"], ResolutionActionCode>> = {
  REFUND_WITHOUT_INVENTORY_RETURN: "REQUEST_INVENTORY_VERIFICATION",
  REFUND_WITHOUT_ERP_REVERSAL: "REQUEST_ERP_INVOICE_CORRECTION",
  MISSING_SETTLEMENT: "REQUEST_SETTLEMENT_REVIEW",
  SETTLEMENT_TIMING: "MARK_AS_TIMING_DIFFERENCE",
  SETTLEMENT_FEE_VARIANCE: "MARK_AS_EXPECTED_FEE_VARIANCE",
  ERP_INVOICE_MISSING: "REQUEST_ERP_INVOICE_CORRECTION",
  ERP_AMOUNT_MISMATCH: "REQUEST_ERP_INVOICE_CORRECTION",
  DUPLICATE_PAYMENT: "REQUEST_REFUND_REVIEW",
  AMBIGUOUS_ASSOCIATION: "ESCALATE_TO_CONTROLLER",
  MANUAL_WORKFLOW_ANOMALY: "ESCALATE_TO_FINANCE_MANAGER"
};

export function ExceptionDetail({ id }: { id: string }) {
  const fallback = exceptionDetails[id] ?? exceptionDetails["EXC-1042"];
  const [exception, setException] = React.useState(fallback);
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
  const [graph, setGraph] = React.useState<import("../lib/types").ApiLifecycleGraph | null>(null);
  React.useEffect(() => { fetchException(id).then(apiException => setException(mapApiException(apiException, fallback))).catch(() => undefined); }, [id, fallback]);
  async function investigate() {
    setInvestigating(true); setInvestigationError(null);
    try { setInvestigation(mapApiInvestigation(await startInvestigation(id, `investigation-${id}`))); }
    catch { setInvestigationError("The investigation service is unavailable. Deterministic evidence remains available for manual review."); }
    finally { setInvestigating(false); }
  }
  async function requestReview() {
    setRequesting(true); setRequestError(null);
    try { await requestResolution(id, reviewActionByType[exception.type] ?? "REQUEST_REFUND_REVIEW", `review-${id}-${Date.now()}`); setRequested(true); }
    catch { setRequestError("The review request could not be recorded. Check that the API is available and try again."); }
    finally { setRequesting(false); }
  }
  async function viewGraph() {
    if (graph) { setGraphVisible(value => !value); return; }
    setGraphLoading(true); setGraphError(null);
    try { setGraph(await fetchExceptionGraph(id)); setGraphVisible(true); }
    catch { setGraphError("The lifecycle graph could not be loaded. The canonical lifecycle remains available below."); }
    finally { setGraphLoading(false); }
  }
  function copyExceptionId() {
    const clipboard = navigator.clipboard;
    if (!clipboard) { setMoreOpen(false); return; }
    clipboard.writeText(exception.id).then(() => setMoreOpen(false)).catch(() => undefined);
  }
  function exportEvidence() {
    downloadCsv(`fintrace-${exception.id}-evidence.csv`, ["Source", "Record ID", "Fact"], exception.investigation.supportingEvidence.map(item => [item.source, item.recordId ?? "", item.fact]));
    setMoreOpen(false);
  }
  return <><div className="mb-5 flex items-center gap-2 text-xs text-muted-foreground"><Link href="/exceptions" className="flex items-center gap-1 font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Exceptions</Link><span>/</span><span>{exception.id}</span></div>{requestError && <Alert variant="destructive" className="mb-4 text-xs">{requestError}</Alert>}<div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-start"><div><div className="mb-2 flex flex-wrap items-center gap-2"><span className="font-mono text-[11px] font-semibold text-muted-foreground">{exception.id}</span><SeverityBadge severity={exception.severity} /><StatusBadge status={requested ? "IN_REVIEW" : exception.status} /></div><h1 className="text-[26px] font-bold tracking-[-0.03em] text-foreground">{exception.label}</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">{exception.summary}</p></div><div className="relative flex items-center gap-2"><Button variant="outline" size="sm" onClick={() => setMoreOpen(value => !value)} aria-expanded={moreOpen}><MoreHorizontal className="h-3.5 w-3.5" />More</Button>{moreOpen && <div role="menu" className="absolute right-0 top-10 z-10 w-48 rounded-lg border border-border bg-card p-1 shadow-lg"><Button variant="ghost" size="sm" className="w-full justify-start" onClick={copyExceptionId}>Copy exception ID</Button><Button variant="ghost" size="sm" className="w-full justify-start" onClick={exportEvidence}>Export evidence</Button><Button asChild variant="ghost" size="sm" className="w-full justify-start"><Link href="/patterns">Review patterns</Link></Button></div>}<Button size="sm" onClick={requestReview} disabled={requested || requesting}>{requesting ? <><Play className="h-3.5 w-3.5 animate-pulse" />Requesting…</> : requested ? <><Check className="h-3.5 w-3.5" />Review requested</> : <><Play className="h-3.5 w-3.5" />Request review</>}</Button></div></div><div className="mb-5 grid gap-4 sm:grid-cols-3"><SummaryCard label="Financial exposure" value={formatCurrency(exception.exposure)} detail="Requires controlled review" tone="destructive" /><SummaryCard label="Lifecycle" value={exception.orderId} detail={`${exception.ruleCount} deterministic rules triggered`} /><SummaryCard label="Policy owner" value={exception.policy.owner} detail={exception.policy.state} /></div><div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]"><div className="space-y-5"><LifecycleCard exception={exception} graphVisible={graphVisible} graphLoading={graphLoading} graphError={graphError} graph={graph} onViewGraph={viewGraph} /><TimelineCard exception={exception} /><AuditCard exception={exception} /></div><div className="space-y-5"><Card className="border-border"><CardHeader className="border-b border-border bg-muted/30"><div className="flex items-center gap-2"><div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10 text-accent"><Sparkles className="h-4 w-4" /></div><div><CardTitle>Evidence investigation</CardTitle><p className="mt-1 text-xs text-muted-foreground">Bounded, read-only AI analysis</p></div></div></CardHeader><CardContent className="p-5">{investigationError && <Alert variant="destructive" className="mb-4">{investigationError}</Alert>}{!investigation ? <div><div className="rounded-lg border border-accent/20 bg-accent/5 p-4"><div className="flex gap-3"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-accent" /><p className="text-xs leading-5 text-muted-foreground">FinTrace will inspect only relevant, organization-scoped evidence using six approved read-only tools. No financial action will be taken.</p></div></div><Button className="mt-4 w-full" onClick={investigate} disabled={investigating}><Sparkles className="h-3.5 w-3.5" />{investigating ? "Investigating…" : "Investigate exception"}</Button><div className="mt-3 text-center text-[10px] text-muted-foreground">Typical investigation time · under 3 seconds</div></div> : <InvestigationResult investigation={investigation} />}</CardContent></Card><PolicyCard exception={exception} /><SimilarIncidents /></div></div></>;
}

function mapApiException(item: ApiExceptionSummary, fallback: ExceptionDetailType): ExceptionDetailType {
  return { ...fallback, id: item.id, orderId: item.order_id, severity: item.severity, status: item.status, exposure: Number(item.financial_exposure), ruleCount: item.rules_triggered.length, summary: `${item.rules_triggered.length} deterministic rule${item.rules_triggered.length === 1 ? "" : "s"} triggered.` };
}

function mapApiInvestigation(item: ApiInvestigation): Investigation {
  return { status: item.status, rootCause: item.root_cause_code ?? "Unresolved", rootCauseCode: item.root_cause_code ?? "UNKNOWN", summary: item.summary, evidenceScore: item.evidence_score, supportingEvidence: item.supporting_evidence.map(evidence => ({ ...evidence, tone: "positive" as const })), contradictoryEvidence: item.contradictory_evidence.map(evidence => ({ ...evidence, tone: "warning" as const })), missingEvidence: item.missing_evidence, action: item.recommended_action_code ?? "Manual review", actionCode: item.recommended_action_code ?? "REQUEST_MANUAL_REVIEW", requiresHumanReview: item.requires_human_review, tools: item.tool_calls.map(call => ({ name: call.name, target: call.target, duration: `${call.duration_ms}ms` })) };
}

function SummaryCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: "destructive" }) {
  return <Card><CardContent className="p-4"><div className="text-[11px] font-medium text-muted-foreground">{label}</div><div className="mt-2 text-xl font-bold tracking-tight text-foreground">{value}</div><div className={cn("mt-1 text-[11px]", tone === "destructive" ? "text-destructive" : "text-muted-foreground")}>{detail}</div></CardContent></Card>;
}

function LifecycleCard({ exception, graphVisible, graphLoading, graphError, graph, onViewGraph }: { exception: ExceptionDetailType; graphVisible: boolean; graphLoading: boolean; graphError: string | null; graph: import("../lib/types").ApiLifecycleGraph | null; onViewGraph: () => void }) {
  return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Transaction lifecycle</CardTitle><p className="mt-1 text-xs text-muted-foreground">Canonical records connected to {exception.orderId}</p></div><Button variant="link" size="sm" onClick={onViewGraph} disabled={graphLoading}>{graphLoading ? "Loading graph…" : graphVisible ? "Hide graph" : "View graph"} <ArrowRight className="h-3.5 w-3.5" /></Button></CardHeader><CardContent><div className="grid gap-2 sm:grid-cols-2">{exception.lifecycle.map(record => { const style = lifecycleStyles[record.status]; return <div key={`${record.source}-${record.id}`} className={cn("rounded-lg border p-3", style.surface)}><div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><span className={cn("flex h-5 w-5 items-center justify-center rounded-full", style.marker)}>{style.icon}</span><span className="text-xs font-semibold text-foreground">{record.source}</span></div><span className="font-mono text-[10px] text-muted-foreground">{record.id}</span></div>{record.amount && <div className="mt-3 text-sm font-bold text-foreground">{record.amount}</div>}<div className="mt-1 text-[11px] text-muted-foreground">{record.detail}</div></div>; })}</div>{graphError && <Alert variant="warning" className="mt-4 text-xs">{graphError}</Alert>}{graphVisible && graph && <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4"><div className="mb-3 flex items-center justify-between"><div className="text-xs font-semibold text-foreground">Derived event graph</div><div className="text-[10px] text-muted-foreground">{graph.nodes.length} nodes · {graph.edges.length} links</div></div><div className="grid gap-2 sm:grid-cols-2">{graph.nodes.map(node => <div key={node.id} className={cn("rounded-md border px-3 py-2", node.state === "MISSING" ? "border-destructive/30 bg-destructive/5" : "border-border bg-card")}><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold text-foreground">{node.label}</span><span className={cn("font-mono text-[9px]", node.state === "MISSING" ? "text-destructive" : "text-muted-foreground")}>{node.state}</span></div><div className="mt-1 font-mono text-[10px] text-muted-foreground">{node.id}</div></div>)}</div><div className="mt-3 space-y-1 border-t border-border pt-3">{graph.edges.map(edge => <div key={`${edge.source}-${edge.target}-${edge.relationship}`} className="font-mono text-[9px] text-muted-foreground">{edge.source} → {edge.target} · {edge.relationship}</div>)}</div></div>}</CardContent></Card>;
}

function TimelineCard({ exception }: { exception: ExceptionDetailType }) {
  return <Card><CardHeader><CardTitle>Incident timeline</CardTitle><p className="mt-1 text-xs text-muted-foreground">Chronological activity across connected source systems</p></CardHeader><CardContent><div className="relative ml-2 border-l border-border pl-6">{exception.timeline.map(event => <div key={`${event.time}-${event.title}`} className="relative pb-6 last:pb-0"><span className={cn("absolute -left-[31px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-card", event.state === "complete" ? "bg-success" : event.state === "warning" ? "bg-warning" : "bg-destructive")}>{event.state === "complete" && <Check className="h-2.5 w-2.5 text-success-foreground" />}</span><div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-xs font-semibold text-foreground">{event.title}</div><div className="mt-1 text-[11px] text-muted-foreground">{event.detail}</div></div><div className="flex items-center gap-2 text-[10px] text-muted-foreground"><span>{event.source}</span><span className="font-mono">{event.time}</span></div></div></div>)}</div></CardContent></Card>;
}

function AuditCard({ exception }: { exception: ExceptionDetailType }) {
  return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Audit history</CardTitle><p className="mt-1 text-xs text-muted-foreground">Append-only record of actions on this exception</p></div><ShieldCheck className="h-4 w-4 text-success" /></CardHeader><CardContent className="p-0"><div className="divide-y divide-border">{exception.audit.map(event => <div key={`${event.time}-${event.action}`} className="flex items-center gap-3 px-5 py-3.5"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted"><FileText className="h-3.5 w-3.5 text-muted-foreground" /></div><div className="min-w-0 flex-1"><div className="text-xs font-semibold text-foreground">{event.action}</div><div className="mt-0.5 truncate text-[11px] text-muted-foreground">{event.actor} · {event.detail}</div></div><span className="font-mono text-[10px] text-muted-foreground">{event.time}</span></div>)}</div></CardContent></Card>;
}

function PolicyCard({ exception }: { exception: ExceptionDetailType }) {
  return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Approval guardrail</CardTitle><p className="mt-1 text-xs text-muted-foreground">Why this incident cannot auto-resolve</p></div><LockKeyhole className="h-4 w-4 text-muted-foreground" /></CardHeader><CardContent><div className="flex items-start gap-3"><div className="mt-0.5 h-2 w-2 rounded-full bg-warning" /><div><div className="text-xs font-semibold text-foreground">{exception.policy.state}</div><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{exception.policy.reason}. The recommended action is simulated and requires a {exception.policy.owner.toLowerCase()} decision.</p></div></div><div className="mt-4 flex items-center gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground"><UserRound className="h-3.5 w-3.5" />Current actor: {appConfig.actor.name} · {appConfig.actor.role}</div></CardContent></Card>;
}

function SimilarIncidents() {
  return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Similar incidents</CardTitle><p className="mt-1 text-xs text-muted-foreground">Linked by rule and workflow</p></div><Badge variant="muted">12 found</Badge></CardHeader><CardContent><div className="flex items-center justify-between"><div><div className="text-lg font-bold text-foreground">₹71,420</div><div className="mt-1 text-[11px] text-muted-foreground">associated exposure this month</div></div><div className="h-12 w-24"><div className="flex h-full items-end gap-1">{[20, 28, 24, 40, 36, 56, 48, 70, 64, 86].map((height, index) => <span key={index} className="flex-1 rounded-t-sm bg-destructive/25" style={{ height: `${height}%` }} />)}</div></div></div><Button asChild variant="link" className="mt-4 w-full justify-between border-t border-border pt-3"><Link href="/patterns">Review pattern <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card>;
}

function InvestigationResult({ investigation }: { investigation: ExceptionDetailType["investigation"] }) {
  return <div><div className="flex items-center justify-between"><div className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-success/10 text-success"><Check className="h-3.5 w-3.5" /></span><span className="text-xs font-bold text-success">{investigation.status}</span></div><span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Verified result</span></div><div className="mt-4 text-sm font-bold text-foreground">{investigation.rootCause}</div><p className="mt-2 text-xs leading-5 text-muted-foreground">{investigation.summary}</p><div className="mt-5 rounded-lg border border-border p-3"><div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-muted-foreground">Evidence score</span><span className="text-sm font-bold text-foreground">{investigation.evidenceScore}<span className="text-[11px] font-medium text-muted-foreground">/100</span></span></div><Progress value={investigation.evidenceScore} className="mt-2" /><div className="mt-2 text-[10px] text-muted-foreground">Strong evidence · not an AI confidence score</div></div><div className="mt-5"><div className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Supporting evidence</div><div className="space-y-2">{investigation.supportingEvidence.map(item => <div key={`${item.source}-${item.fact}`} className="flex gap-2 text-[11px] leading-4"><span className={cn("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", item.tone === "positive" ? "bg-success" : item.tone === "warning" ? "bg-destructive" : "bg-muted-foreground")} /><span className="text-muted-foreground"><strong className="font-semibold text-foreground">{item.source}:</strong> {item.fact}</span></div>)}</div></div><div className="mt-5 rounded-lg bg-info/10 p-3"><div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-info"><ArrowRight className="h-3.5 w-3.5" />Recommended next action</div><div className="mt-1.5 text-xs font-semibold text-info">{investigation.action}</div><div className="mt-2 text-[10px] leading-4 text-info">Human review required. No resolution performed.</div></div><div className="mt-5 border-t border-border pt-4"><div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground"><span>Read-only tool calls</span><span>{investigation.tools.length} tools</span></div><div className="space-y-1.5">{investigation.tools.map(tool => <div key={tool.name} className="flex items-center justify-between rounded bg-muted px-2.5 py-2 font-mono text-[10px]"><span className="text-muted-foreground">{tool.name}<span className="text-muted-foreground">({tool.target})</span></span><span className="text-muted-foreground">{tool.duration}</span></div>)}</div></div></div>;
}
