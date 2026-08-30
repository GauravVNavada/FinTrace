"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, CalendarDays, Check, ChevronRight, CircleAlert, Clock3, Download, ExternalLink, Filter, LockKeyhole, MoreHorizontal, Play, RefreshCw, ShieldCheck, Sparkles, TrendingUp } from "lucide-react";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Input, Progress, Select, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, cn } from "@fintrace/ui";
import { appConfig, exceptionItems, formatCurrency, healthBreakdown, metrics, patterns, recentRuns } from "../lib/data";
import { fetchExceptions } from "../lib/api-client";
import type { ExceptionItem, Metric } from "../lib/types";
import { SeverityBadge, StatusBadge } from "./status-badge";

const bars = [38, 44, 40, 54, 48, 62, 58, 76, 64, 72, 82, 68, 86, 78, 94, 88, 100, 92, 74, 80, 68, 70, 61, 66, 59, 55, 58, 51, 48, 44];
const healthTone: Record<string, string> = { success: "bg-success", warning: "bg-warning", destructive: "bg-destructive", muted: "bg-muted-foreground" };

const exceptionLabels: Record<string, string> = {
  REFUND_WITHOUT_INVENTORY_RETURN: "Refund without inventory return",
  MISSING_SETTLEMENT: "Missing settlement",
  DUPLICATE_PAYMENT: "Duplicate payment",
  ERP_INVOICE_MISSING: "ERP invoice missing",
  ERP_AMOUNT_MISMATCH: "ERP amount mismatch",
  SETTLEMENT_TIMING: "Settlement timing difference",
  MANUAL_WORKFLOW_ANOMALY: "Manual workflow anomaly",
  REFUND_WITHOUT_ERP_REVERSAL: "Refund without ERP reversal"
};

function mapException(item: import("../lib/types").ApiExceptionSummary): ExceptionItem {
  return {
    id: item.id,
    orderId: item.order_id,
    type: item.type,
    label: exceptionLabels[item.type] ?? item.type.replaceAll("_", " "),
    severity: item.severity,
    status: item.status,
    exposure: Number(item.financial_exposure),
    currency: "INR",
    detectedAt: new Date(item.detected_at).toLocaleString(),
    summary: `${item.rules_triggered.length} deterministic rule${item.rules_triggered.length === 1 ? "" : "s"} triggered.`,
    source: "Deterministic reconciliation",
    ruleCount: item.rules_triggered.length,
    assignee: "Unassigned"
  };
}

function useExceptionItems(fallback: ExceptionItem[]) {
  const [items, setItems] = React.useState(fallback);
  React.useEffect(() => {
    let active = true;
    fetchExceptions().then(response => { if (active) setItems(response.map(mapException)); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  return items;
}

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground"><span>{eyebrow}</span><span className="h-1 w-1 rounded-full bg-border" />{appConfig.batchName}</div><h1 className="text-[28px] font-bold tracking-[-0.03em] text-foreground">{title}</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p></div><div className="flex items-center gap-2">{children}</div></div>;
}

function MetricCard({ label, value, detail, trend, tone }: Metric) {
  const positive = tone === "positive" || trend?.startsWith("+");
  return <Card><CardContent className="p-5"><div className="flex items-start justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{label}</span>{trend && <span className={cn("flex items-center gap-0.5 text-[11px] font-bold", positive ? "text-success" : tone === "critical" ? "text-destructive" : "text-warning-foreground")}>{positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}{trend}</span>}</div><div className="mt-3 text-[25px] font-bold tracking-tight text-foreground">{value}</div><div className="mt-1 text-[11px] text-muted-foreground">{detail}</div></CardContent></Card>;
}

function HealthCard() {
  return <Card className="lg:col-span-5"><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Reconciliation health</CardTitle><p className="mt-1 text-xs text-muted-foreground">Across the current batch</p></div><Button variant="ghost" size="icon" aria-label="More reconciliation health options"><MoreHorizontal className="h-4 w-4" /></Button></CardHeader><CardContent><div className="mb-5 flex h-3 overflow-hidden rounded-full bg-muted">{healthBreakdown.map(item => <div key={item.label} className={healthTone[item.tone]} style={{ width: `${item.percent}%` }} />)}</div><div className="grid grid-cols-2 gap-x-6 gap-y-4">{healthBreakdown.map(item => <div key={item.label} className="flex items-center justify-between"><div className="flex items-center gap-2 text-xs text-muted-foreground"><span className={cn("h-2 w-2 rounded-full", healthTone[item.tone])} />{item.label}</div><span className="text-xs font-bold text-foreground">{item.value.toLocaleString()}</span></div>)}</div><div className="mt-6 border-t border-border pt-4"><div className="flex items-center justify-between text-xs"><span className="font-medium text-muted-foreground">Auto-reconciliation rate</span><span className="font-bold text-success">86.7%</span></div><Progress value={86.7} className="mt-2" /></div></CardContent></Card>;
}

function ThroughputCard() {
  return <Card className="lg:col-span-7"><CardHeader className="flex-row items-start justify-between"><div><CardTitle>Processing throughput</CardTitle><p className="mt-1 text-xs text-muted-foreground">Records reconciled · last 30 runs</p></div><div className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground"><CalendarDays className="h-3.5 w-3.5" />30 days</div></CardHeader><CardContent><div className="flex items-end justify-between"><div><span className="text-[26px] font-bold tracking-tight text-foreground">428</span><span className="ml-2 text-xs text-muted-foreground">records / second</span><div className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-success"><TrendingUp className="h-3 w-3" />12.4% vs previous period</div></div><div className="rounded-md bg-success/10 px-2 py-1 text-[11px] font-semibold text-success">Healthy</div></div><div className="mt-6 flex h-[88px] items-end gap-1.5">{bars.map((height, index) => <div key={index} className="group relative flex-1"><div className={cn("w-full rounded-t-sm transition-colors group-hover:bg-primary", index > 25 ? "bg-muted" : "bg-muted-foreground/40")} style={{ height: `${height}%` }} /></div>)}</div><div className="mt-2 flex justify-between text-[10px] text-muted-foreground"><span>01 Aug</span><span>15 Aug</span><span>30 Aug</span></div></CardContent></Card>;
}

function ExceptionQueue({ items = exceptionItems, compact = false }: { items?: ExceptionItem[]; compact?: boolean }) {
  const liveItems = useExceptionItems(items);
  return <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>{compact ? "Priority exceptions" : "Exception queue"}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{compact ? "The incidents requiring attention first" : "All unresolved lifecycle breaks in this run"}</p></div><div className="flex items-center gap-2"><Button variant="outline" size="icon" className="hidden sm:inline-flex" aria-label="Filter exceptions"><Filter className="h-3.5 w-3.5" /></Button><Button asChild variant="link" size="sm"><Link href="/exceptions">View all <ChevronRight className="h-3.5 w-3.5" /></Link></Button></div></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow className="bg-muted/50"><TableHead>Exception</TableHead><TableHead>Severity</TableHead><TableHead>Status</TableHead><TableHead>Exposure</TableHead><TableHead>Detected</TableHead><TableHead /></TableRow></TableHeader><TableBody>{liveItems.slice(0, compact ? 4 : 10).map(item => <TableRow key={item.id}><TableCell><Link href={`/exceptions/${item.id}`} className="group block"><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{item.id}</span><span className="text-xs font-semibold text-foreground group-hover:text-primary">{item.label}</span></div><div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground"><span>{item.orderId}</span><span>·</span><span>{item.source}</span></div></Link></TableCell><TableCell><SeverityBadge severity={item.severity} /></TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell className="text-xs font-semibold text-foreground">{formatCurrency(item.exposure)}</TableCell><TableCell className="text-xs text-muted-foreground">{item.detectedAt}</TableCell><TableCell className="text-right"><Button asChild variant="ghost" size="icon" aria-label={`Open ${item.id}`}><Link href={`/exceptions/${item.id}`}><ChevronRight className="h-4 w-4" /></Link></Button></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}

export function Overview() {
  return <><PageHeading eyebrow="Control center" title={`Good afternoon, ${appConfig.actor.firstName}`} description="A clear view of financial integrity across your transaction lifecycles."><Button variant="outline" size="sm"><Download className="h-3.5 w-3.5" />Export report</Button><Button size="sm"><RefreshCw className="h-3.5 w-3.5" />Run reconciliation</Button></PageHeading><div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(metric => <MetricCard key={metric.label} {...metric} />)}</div><div className="mb-6 grid gap-4 lg:grid-cols-12"><HealthCard /><ThroughputCard /></div><div className="mb-6"><ExceptionQueue compact /></div><div className="grid gap-4 lg:grid-cols-12"><Card className="lg:col-span-7"><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Recurring patterns</CardTitle><p className="mt-1 text-xs text-muted-foreground">Signals found across related exceptions</p></div><Button asChild variant="link" size="sm"><Link href="/patterns">See patterns <ChevronRight className="h-3.5 w-3.5" /></Link></Button></CardHeader><CardContent className="space-y-4">{patterns.slice(0, 2).map(pattern => <div key={pattern.id} className="flex items-start gap-3 rounded-lg border border-border p-3.5"><div className="mt-0.5 rounded-md bg-destructive/10 p-2 text-destructive"><CircleAlert className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><div className="text-xs font-semibold text-foreground">{pattern.title}</div><SeverityBadge severity={pattern.severity} /></div><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{pattern.description}</p><div className="mt-2 flex gap-4 text-[10px] text-muted-foreground"><span><strong className="text-foreground">{pattern.incidents}</strong> incidents</span><span><strong className="text-foreground">{formatCurrency(pattern.exposure)}</strong> exposure</span><span>{pattern.location}</span></div></div></div>)}</CardContent></Card><Card className="lg:col-span-5"><CardHeader><CardTitle>Control posture</CardTitle><p className="mt-1 text-xs text-muted-foreground">Guardrails are active for this workspace</p></CardHeader><CardContent className="space-y-4">{[{ icon: ShieldCheck, title: "Deterministic matching", detail: "No AI in financial calculations", tone: "text-success bg-success/10" }, { icon: LockKeyhole, title: "Approval gates", detail: "High-value actions require review", tone: "text-info bg-info/10" }, { icon: Sparkles, title: "Evidence-bounded AI", detail: "Read-only investigation tools", tone: "text-accent bg-accent/10" }].map(item => <div key={item.title} className="flex items-center gap-3"><div className={cn("rounded-md p-2", item.tone)}><item.icon className="h-4 w-4" /></div><div><div className="text-xs font-semibold text-foreground">{item.title}</div><div className="mt-0.5 text-[11px] text-muted-foreground">{item.detail}</div></div><Check className="ml-auto h-4 w-4 text-success" /></div>)}</CardContent></Card></div></>;
}

export function ExceptionsPage() {
  const [query, setQuery] = React.useState("");
  const [severity, setSeverity] = React.useState("ALL");
  const [status, setStatus] = React.useState("ALL");
  const liveItems = useExceptionItems(exceptionItems);
  const filtered = liveItems.filter(item => `${item.id} ${item.orderId} ${item.label}`.toLowerCase().includes(query.toLowerCase()) && (severity === "ALL" || item.severity === severity) && (status === "ALL" || item.status === status));
  return <><PageHeading eyebrow="Exceptions" title="Exception queue" description="Investigate the lifecycle breaks that deterministic reconciliation could not safely close."><Button variant="outline" size="sm"><Download className="h-3.5 w-3.5" />Export queue</Button></PageHeading><div className="mb-4 flex flex-col gap-2 rounded-xl border border-border bg-card p-3 sm:flex-row"><div className="relative flex-1"><Filter className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input value={query} onChange={event => setQuery(event.target.value)} aria-label="Search exception queue" placeholder="Search exception ID, order or type" className="bg-muted/50 pl-9 text-xs" /></div><Select aria-label="Filter by severity" value={severity} onChange={event => setSeverity(event.target.value)} className="sm:w-40"><option value="ALL">All severity</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></Select><Select aria-label="Filter by status" value={status} onChange={event => setStatus(event.target.value)} className="sm:w-40"><option value="ALL">All status</option><option value="OPEN">Open</option><option value="IN_REVIEW">In review</option><option value="ESCALATED">Escalated</option><option value="RESOLVED">Resolved</option></Select></div><Card><CardContent className="p-0"><div className="flex items-center justify-between border-b border-border px-5 py-4"><div className="text-xs text-muted-foreground"><span className="font-semibold text-foreground">{filtered.length}</span> visible in current queue</div><div className="flex items-center gap-2 text-[11px] text-muted-foreground"><Clock3 className="h-3.5 w-3.5" />Sorted by severity and age</div></div><ExceptionTable items={filtered} /></CardContent></Card></>;
}

function ExceptionTable({ items }: { items: ExceptionItem[] }) {
  return <>{items.length === 0 ? <Alert variant="info" className="m-5 text-center">No exceptions match these filters. Try widening the search or clearing a filter.</Alert> : <Table><TableHeader><TableRow className="bg-muted/50"><TableHead>Exception</TableHead><TableHead>Severity</TableHead><TableHead>Status</TableHead><TableHead>Exposure</TableHead><TableHead>Owner</TableHead><TableHead>Detected</TableHead><TableHead /></TableRow></TableHeader><TableBody>{items.map(item => <TableRow key={item.id}><TableCell><Link href={`/exceptions/${item.id}`} className="group block"><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{item.id}</span><span className="text-xs font-semibold text-foreground group-hover:text-primary">{item.label}</span></div><div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground"><span>{item.orderId}</span><span>·</span><span>{item.summary}</span></div></Link></TableCell><TableCell><SeverityBadge severity={item.severity} /></TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell className="text-xs font-semibold text-foreground">{formatCurrency(item.exposure)}</TableCell><TableCell className="text-xs text-muted-foreground">{item.assignee}</TableCell><TableCell className="text-xs text-muted-foreground">{item.detectedAt}</TableCell><TableCell className="text-right"><Button asChild variant="outline" size="sm"><Link href={`/exceptions/${item.id}`}>Inspect <ExternalLink className="h-3 w-3" /></Link></Button></TableCell></TableRow>)}</TableBody></Table>}</>;
}

export function RunsPage() { return <><PageHeading eyebrow="Controls" title="Reconciliation runs" description="A reproducible history of each batch processed through the deterministic engine."><Button size="sm"><Play className="h-3.5 w-3.5" />Start new run</Button></PageHeading><Card><CardContent className="p-0"><Table><TableHeader><TableRow className="bg-muted/50"><TableHead>Run</TableHead><TableHead>Records</TableHead><TableHead>Match rate</TableHead><TableHead>Exceptions</TableHead><TableHead>Completed</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{recentRuns.map(run => <TableRow key={run.name}><TableCell className="font-semibold text-foreground">{run.name}<div className="mt-1 font-mono text-[10px] font-normal text-muted-foreground">seed 42 · deterministic</div></TableCell><TableCell>{run.records}</TableCell><TableCell className="font-semibold text-success">{run.match}</TableCell><TableCell>{run.exceptions}</TableCell><TableCell className="text-muted-foreground">{run.completed}</TableCell><TableCell><span className="inline-flex items-center gap-1.5 font-semibold text-success"><span className="h-1.5 w-1.5 rounded-full bg-success" />{run.status}</span></TableCell></TableRow>)}</TableBody></Table></CardContent></Card></>; }

export function SettingsPage() { return <><PageHeading eyebrow="Workspace" title="Settings" description="Workspace configuration and policy controls for Northstar Retail Group." /><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Workspace details</CardTitle></CardHeader><CardContent className="space-y-4">{[["Workspace name", appConfig.workspaceName], ["Environment", appConfig.workspaceEnvironment], ["Currency", "INR · Indian Rupee"], ["Dataset mode", "Synthetic demo data"]].map(row => <div key={row[0]} className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0"><span className="text-xs text-muted-foreground">{row[0]}</span><span className="text-xs font-semibold text-foreground">{row[1]}</span></div>)}</CardContent></Card><Card><CardHeader><CardTitle>Approval policy</CardTitle></CardHeader><CardContent className="space-y-4">{[["₹0–₹10,000", "Finance Manager"], ["₹10,001–₹1,00,000", "Controller"], [">₹1,00,000", "Controller + secondary approval"]].map(row => <div key={row[0]} className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0"><span className="font-mono text-xs text-muted-foreground">{row[0]}</span><span className="text-xs font-semibold text-foreground">{row[1]}</span></div>)}</CardContent></Card></div></>; }
