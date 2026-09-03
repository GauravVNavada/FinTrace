"use client";

import * as React from "react";
import Link from "next/link";
import { Activity, AlertCircle, Clock3, Download, ExternalLink, Filter, Play, RefreshCw } from "lucide-react";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Input, Select, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@fintrace/ui";
import { appConfig } from "../lib/data";
import { ApiClientError, fetchExceptions, fetchFinancialInvestigationPatterns, fetchFinancialInvestigations, fetchLatestEvaluation, fetchLatestReconciliation, runEvaluation } from "../lib/api-client";
import { downloadCsv } from "../lib/export";
import type { ApiEvaluation, ApiExceptionSummary, ApiFinancialInvestigation, ApiFinancialInvestigationPattern, ApiReconciliationRun, ExceptionItem } from "../lib/types";
import { SeverityBadge, StatusBadge } from "./status-badge";

const exceptionLabels: Record<string, string> = {
  REFUND_WITHOUT_INVENTORY_RETURN: "Refund without inventory return",
  MISSING_SETTLEMENT: "Missing settlement",
  DUPLICATE_PAYMENT: "Duplicate payment",
  ERP_INVOICE_MISSING: "ERP invoice missing",
  ERP_AMOUNT_MISMATCH: "ERP amount mismatch",
  SETTLEMENT_TIMING: "Settlement timing difference",
  MANUAL_WORKFLOW_ANOMALY: "Manual workflow anomaly",
  REFUND_WITHOUT_ERP_REVERSAL: "Refund without ERP reversal",
  PARTIAL_REFUND_MISMATCH: "Partial refund mismatch",
  SETTLEMENT_FEE_VARIANCE: "Settlement fee variance",
  PAYMENT_FEE_MISSING: "Payment fee missing",
  SETTLEMENT_FEE_MISSING: "Settlement fee missing",
};

function createActionKey(prefix: string): string {
  return `${prefix}-${Date.now()}`;
}

function formatMinor(value: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(value / 100);
}

function mapException(item: ApiExceptionSummary): ExceptionItem {
  return {
    id: item.id,
    orderId: item.order_id,
    type: item.type,
    label: exceptionLabels[item.type] ?? item.type.replaceAll("_", " "),
    severity: item.severity,
    status: item.status,
    exposure: Number(item.financial_exposure),
    currency: item.currency,
    detectedAt: new Date(item.detected_at).toLocaleString(),
    summary: `${item.rules_triggered.length} deterministic rule${item.rules_triggered.length === 1 ? "" : "s"} triggered.`,
    source: "Deterministic reconciliation",
    ruleCount: item.rules_triggered.length,
    assignee: "Unassigned",
  };
}

function useExceptionItems() {
  const [items, setItems] = React.useState<ExceptionItem[]>([]);
  const [unavailable, setUnavailable] = React.useState(false);
  React.useEffect(() => {
    let active = true;
    fetchExceptions()
      .then(response => { if (active) setItems(response.map(mapException)); })
      .catch(() => { if (active) setUnavailable(true); });
    return () => { active = false; };
  }, []);
  return { items, unavailable };
}

export function ActionNotice({ message, variant = "info" }: { message: string | null; variant?: "info" | "warning" | "destructive" }) {
  return message ? <Alert variant={variant} className="mb-4 text-xs" aria-live="polite">{message}</Alert> : null;
}

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground"><span>{eyebrow}</span><span className="h-1 w-1 rounded-full bg-border" /><span>{appConfig.workspaceEnvironment}</span></div><h1 className="text-[28px] font-bold tracking-[-0.03em] text-foreground">{title}</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p></div><div className="flex items-center gap-2">{children}</div></div>;
}

export function Overview() {
  const [investigations, setInvestigations] = React.useState<ApiFinancialInvestigation[]>([]);
  const [selected, setSelected] = React.useState<ApiFinancialInvestigation | null>(null);
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [patterns, setPatterns] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [unavailable, setUnavailable] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    fetchFinancialInvestigations()
      .then(items => {
        if (!active) return;
        setInvestigations(items);
        const requestedId = new URLSearchParams(window.location.search).get("investigation");
        const current = items.find(item => item.id === requestedId) ?? (items.length === 1 ? items[0] : null);
        setSelected(current);
        if (!current) return;
        return Promise.all([
          fetchLatestReconciliation(current.id).catch(() => null),
          fetchFinancialInvestigationPatterns(current.id).catch(() => []),
        ]).then(([latestRun, latestPatterns]) => {
          if (!active) return;
          setRun(latestRun);
          setPatterns(latestPatterns);
        });
      })
      .catch(() => { if (active) setUnavailable(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function exportReport() {
    if (!selected || !run) return;
    downloadCsv("fintrace-investigation-report.csv", ["Metric", "Value", "Detail"], [
      ["Investigation", selected.name, ""],
      ["Lifecycles", run.lifecycle_count, "Latest persisted reconciliation run"],
      ["Reconciled", run.reconciled_count, "Deterministic outcomes"],
      ["Exceptions", run.exception_count + run.ambiguous_count, "Exception and ambiguous outcomes"],
      ["Open exposure", formatMinor(run.open_exposure_minor, selected.base_currency), "Open exposure only"],
    ]);
  }

  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><RefreshCw className="h-4 w-4 animate-spin" />Loading live investigation metrics…</div>;
  if (unavailable) return <><PageHeading eyebrow="Control center" title="Financial integrity workspace" description="The dashboard reads persisted investigation data from the API." /><Alert variant="destructive">The API is unavailable. No stale dashboard snapshot has been substituted.</Alert></>;
  if (!selected) return <><PageHeading eyebrow="Control center" title="Financial integrity workspace" description="Select the investigation you want to inspect. Metrics and patterns never silently switch workspaces."><Button asChild size="sm"><Link href="/investigations/new">Create investigation</Link></Button></PageHeading>{investigations.length > 1 && <Card className="mb-4"><CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"><div><div className="text-sm font-semibold text-foreground">Choose an investigation</div><p className="mt-1 text-xs text-muted-foreground">There are multiple workspaces in this organization.</p></div><Select aria-label="Select investigation" defaultValue="" onChange={event => { if (event.target.value) window.location.href = `/?investigation=${encodeURIComponent(event.target.value)}`; }} className="sm:w-80"><option value="">Select an investigation</option>{investigations.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></CardContent></Card>}{investigations.length <= 1 && <Card><CardContent className="py-16 text-center"><div className="text-sm font-semibold text-foreground">No financial investigation selected</div><p className="mx-auto mt-2 max-w-md text-xs leading-5 text-muted-foreground">Upload source exports, confirm mappings, review deterministic relationships, and run reconciliation before metrics appear here.</p><Button asChild className="mt-5" size="sm"><Link href="/investigations">Open investigations</Link></Button></CardContent></Card>}</>;
  const autoRate = run && run.lifecycle_count > 0 ? Math.round((run.reconciled_count / run.lifecycle_count) * 1000) / 10 : null;
  const metrics = [
    ["Lifecycle records", run ? run.lifecycle_count.toLocaleString() : "—", run ? "Latest run" : "Normalize and reconcile to calculate"],
    ["Auto-reconciled", autoRate === null ? "—" : `${autoRate}%`, run ? `${run.reconciled_count.toLocaleString()} deterministic matches` : "No persisted result"],
    ["Open exposure", run ? formatMinor(run.open_exposure_minor, selected.base_currency) : "—", run ? `${run.exception_count + run.ambiguous_count} outcomes need review` : "No persisted result"],
    ["Patterns", patterns.length.toLocaleString(), "Investigation-scoped advisory signals"],
  ];
  return <><PageHeading eyebrow="Control center" title={selected.name} description="Live metrics from the latest persisted reconciliation run for this investigation."><Button variant="outline" size="sm" onClick={exportReport} disabled={!run}><Download className="h-3.5 w-3.5" />Export report</Button><Button asChild size="sm"><Link href={`/investigations/${selected.id}`}>Open investigation</Link></Button></PageHeading><div className="mb-6 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><span className="font-mono">{selected.id}</span><span>·</span><span>{selected.base_currency}</span><span>·</span><span>{selected.source_file_count} source files</span><span>·</span><span>{run ? `Run completed ${new Date(run.completed_at ?? run.started_at).toLocaleString()}` : "No run completed"}</span></div><div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(([label, value, detail]) => <Card key={label}><CardContent className="p-5"><div className="text-xs font-medium text-muted-foreground">{label}</div><div className="mt-3 text-[25px] font-bold tracking-tight text-foreground">{value}</div><div className="mt-1 text-[11px] text-muted-foreground">{detail}</div></CardContent></Card>)}</div><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Latest reconciliation</CardTitle></CardHeader><CardContent>{run ? <div className="space-y-3 text-xs"><div className="flex items-center justify-between border-b border-border pb-3"><span className="text-muted-foreground">Run status</span><span className="font-semibold text-foreground">{run.status}</span></div><div className="flex items-center justify-between border-b border-border pb-3"><span className="text-muted-foreground">Exceptions</span><span className="font-semibold text-foreground">{run.exception_count + run.ambiguous_count}</span></div><div className="flex items-center justify-between"><span className="text-muted-foreground">Dataset</span><span className="font-mono text-[10px] text-foreground">{run.dataset_version_id}</span></div><Button asChild variant="outline" size="sm" className="mt-3"><Link href={`/investigations/${selected.id}`}>Inspect results</Link></Button></div> : <div><p className="text-xs leading-5 text-muted-foreground">This investigation has no persisted reconciliation run yet. The workflow will block until mappings and relationships are confirmed.</p><Button asChild className="mt-4" size="sm"><Link href={`/investigations/${selected.id}/sources`}>Continue source workflow</Link></Button></div>}</CardContent></Card><Card><CardHeader><CardTitle>Recurring patterns</CardTitle></CardHeader><CardContent>{patterns.length === 0 ? <p className="text-xs leading-5 text-muted-foreground">No investigation-scoped patterns meet the minimum occurrence threshold.</p> : <div className="space-y-3">{patterns.slice(0, 4).map(pattern => <div key={pattern.pattern_id} className="rounded-md border border-border p-3 text-xs"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-foreground">{pattern.exception_type}</span><span className="text-muted-foreground">{pattern.occurrence_count} occurrences</span></div><p className="mt-1 leading-5 text-muted-foreground">{pattern.observation}</p><div className="mt-2 font-semibold text-foreground">{formatMinor(pattern.associated_exposure_minor, selected.base_currency)} exposure</div></div>)}<Button asChild variant="link" size="sm" className="px-0"><Link href="/patterns">View all patterns</Link></Button></div>}</CardContent></Card></div></>;
}

export function ExceptionsPage() {
  const [query, setQuery] = React.useState("");
  const [severity, setSeverity] = React.useState("ALL");
  const [status, setStatus] = React.useState("ALL");
  const { items, unavailable } = useExceptionItems();
  const filtered = items.filter(item => `${item.id} ${item.orderId} ${item.label}`.toLowerCase().includes(query.toLowerCase()) && (severity === "ALL" || item.severity === severity) && (status === "ALL" || item.status === status));
  React.useEffect(() => {
    const initialQuery = new URLSearchParams(window.location.search).get("query");
    if (initialQuery) setQuery(initialQuery);
  }, []);
  function exportQueue() {
    downloadCsv("fintrace-exception-queue.csv", ["ID", "Order", "Type", "Severity", "Status", "Exposure", "Detected", "Owner"], filtered.map(item => [item.id, item.orderId, item.label, item.severity, item.status, item.exposure, item.detectedAt, item.assignee ?? "Unassigned"]));
  }
  return <><PageHeading eyebrow="Exceptions" title="Exception queue" description="Investigate lifecycle breaks that deterministic reconciliation could not safely close."><Button variant="outline" size="sm" onClick={exportQueue} disabled={unavailable || filtered.length === 0}><Download className="h-3.5 w-3.5" />Export queue</Button></PageHeading>{unavailable && <Alert variant="destructive" className="mb-4 text-xs">The exception API is unavailable. No static queue has been substituted.</Alert>}<div id="filters" className="mb-4 flex flex-col gap-2 rounded-xl border border-border bg-card p-3 sm:flex-row"><div className="relative flex-1"><Filter className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input value={query} onChange={event => setQuery(event.target.value)} aria-label="Search exception queue" placeholder="Search exception ID, order or type" /></div><Select aria-label="Filter by severity" value={severity} onChange={event => setSeverity(event.target.value)} className="sm:w-40"><option value="ALL">All severity</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></Select><Select aria-label="Filter by status" value={status} onChange={event => setStatus(event.target.value)} className="sm:w-40"><option value="ALL">All status</option><option value="OPEN">Open</option><option value="IN_REVIEW">In review</option><option value="ESCALATED">Escalated</option><option value="RESOLVED">Resolved</option></Select></div><Card><CardContent className="p-0"><div className="flex items-center justify-between border-b border-border px-5 py-4"><div className="text-xs text-muted-foreground"><span className="font-semibold text-foreground">{filtered.length}</span> visible in current queue</div><div className="flex items-center gap-2 text-[11px] text-muted-foreground"><Clock3 className="h-3.5 w-3.5" />Sorted by severity and age</div></div><ExceptionTable items={filtered} /></CardContent></Card></>;
}

function ExceptionTable({ items }: { items: ExceptionItem[] }) {
  return <>{items.length === 0 ? <Alert variant="info" className="m-5 text-center">No exceptions match these filters or no persisted exception records exist yet.</Alert> : <Table><TableHeader><TableRow className="bg-muted/50"><TableHead>Exception</TableHead><TableHead>Severity</TableHead><TableHead>Status</TableHead><TableHead>Exposure</TableHead><TableHead>Owner</TableHead><TableHead>Detected</TableHead><TableHead /></TableRow></TableHeader><TableBody>{items.map(item => <TableRow key={item.id}><TableCell><Link href={`/exceptions/${item.id}`} className="group block"><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{item.id}</span><span className="text-xs font-semibold text-foreground group-hover:text-primary">{item.label}</span></div><div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground"><span>{item.orderId}</span><span>·</span><span>{item.summary}</span></div></Link></TableCell><TableCell><SeverityBadge severity={item.severity} /></TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell className="text-xs font-semibold text-foreground">{new Intl.NumberFormat("en-IN", { style: "currency", currency: item.currency, maximumFractionDigits: 0 }).format(item.exposure)}</TableCell><TableCell className="text-xs text-muted-foreground">{item.assignee}</TableCell><TableCell className="text-xs text-muted-foreground">{item.detectedAt}</TableCell><TableCell className="text-right"><Button asChild variant="outline" size="sm"><Link href={`/exceptions/${item.id}`}>Inspect <ExternalLink className="h-3 w-3" /></Link></Button></TableCell></TableRow>)}</TableBody></Table>}</>;
}

export function RunsPage() {
  const [latest, setLatest] = React.useState<ApiEvaluation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<ApiClientError | null>(null);
  const [running, setRunning] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [reloadToken, setReloadToken] = React.useState(0);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    fetchLatestEvaluation()
      .then(result => { if (active) { setLatest(result); setLoadError(null); } })
      .catch(error => {
        if (!active) return;
        if (error instanceof ApiClientError && error.status === 404) { setLatest(null); setLoadError(null); }
        else setLoadError(error instanceof ApiClientError ? error : new ApiClientError(0, "The benchmark history could not be loaded.", "UNKNOWN_ERROR"));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reloadToken]);

  async function startRun() {
    setRunning(true); setNotice(null); setLoadError(null);
    try {
      const result = await runEvaluation({ orders: appConfig.benchmark.orders, seed: appConfig.benchmark.seed, anomaly_rate: appConfig.benchmark.anomalyRate }, createActionKey("run"));
      setLatest(result);
      setNotice("Benchmark completed and the result was persisted.");
    } catch (error) {
      setNotice(error instanceof ApiClientError ? error.message : "The benchmark could not be started. Try again.");
    } finally { setRunning(false); }
  }

  const unavailable = loadError !== null && loadError.status !== 403;
  return <>
    <PageHeading eyebrow="Controls" title="Reconciliation evaluation runs" description="A reproducible synthetic benchmark for validating deterministic matching against hidden ground truth.">
      <Button size="sm" onClick={() => void startRun()} disabled={running || loading || loadError?.status === 403} title={loadError?.status === 403 ? "Evaluation access is restricted for this role" : "Generate and persist a synthetic benchmark run"}><Play className={running ? "h-3.5 w-3.5 animate-pulse" : "h-3.5 w-3.5"} />{running ? "Running benchmark…" : "Start benchmark"}</Button>
    </PageHeading>
    <ActionNotice message={notice} variant={notice?.toLowerCase().includes("could not") || notice?.toLowerCase().includes("unavailable") ? "destructive" : "info"} />
    {loadError?.status === 403 && <Alert variant="warning" className="mb-4 flex items-center gap-2 text-xs"><AlertCircle className="h-4 w-4" />Your role cannot view evaluation results. Ask a Controller or Finance Manager for access.</Alert>}
    {unavailable && <Alert variant="destructive" className="mb-4 flex items-center justify-between gap-3 text-xs"><span>{loadError?.message ?? "The evaluation service is unavailable."}</span><Button variant="outline" size="sm" onClick={() => setReloadToken(value => value + 1)}><RefreshCw className="h-3.5 w-3.5" />Retry</Button></Alert>}
    {loading ? <div role="status" aria-label="Loading evaluation history" className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" /></div> : latest ? <RunResult evaluation={latest} /> : !loadError ? <EmptyState icon={<Activity className="h-5 w-5" />} eyebrow="No run history" title="Your first benchmark is ready to run" description="FinTrace will generate synthetic lifecycles, apply deterministic reconciliation rules, and compare the result with hidden ground truth. Nothing in this benchmark changes a real payment or customer record." actions={<Button onClick={() => void startRun()} disabled={running}><Play className="h-3.5 w-3.5" />{running ? "Running…" : "Run first benchmark"}</Button>} /> : null}
  </>;
}

function RunResult({ evaluation }: { evaluation: ApiEvaluation }) {
  const metrics = [
    ["Lifecycles", evaluation.report.lifecycles.toLocaleString()],
    ["Match rate", `${evaluation.report.match_rate}%`],
    ["Match precision", `${evaluation.report.match_precision}%`],
    ["Exceptions", evaluation.report.exceptions.toLocaleString()],
    ["Exception recall", `${evaluation.report.exception_recall}%`],
    ["Severity accuracy", `${evaluation.report.severity_accuracy}%`],
    ["Throughput", `${evaluation.report.throughput_per_second}/s`],
    ["Unresolved", evaluation.report.unresolved_exceptions.toLocaleString()],
  ];
  return <div className="space-y-4">
    <Card><CardHeader className="flex flex-row items-start justify-between gap-4"><div><CardTitle>Latest benchmark run</CardTitle><p className="mt-1 text-xs text-muted-foreground">{new Date(evaluation.created_at).toLocaleString()} · seed {evaluation.seed} · {evaluation.anomaly_rate}% anomaly rate</p></div><span className="rounded-full bg-success/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-success">Persisted</span></CardHeader><CardContent><div className="grid gap-x-5 gap-y-6 text-xs sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([label, value]) => <div key={label}><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div><div className="mt-1 text-xl font-bold text-foreground">{value}</div></div>)}</div></CardContent></Card>
    <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>What this run proves</CardTitle></CardHeader><CardContent className="text-xs leading-5 text-muted-foreground">Deterministic rules were measured against synthetic hidden labels. Match precision, exception recall, severity accuracy, and unsafe-resolution rate are separate signals; a high match rate alone is not a safety claim.</CardContent></Card><Card><CardHeader><CardTitle>Benchmark boundaries</CardTitle></CardHeader><CardContent className="text-xs leading-5 text-muted-foreground">This is a Track 4 reconciliation control benchmark. It does not measure live AI quality, uploaded-investigation outcomes, or production payment processing. Those are reported separately in Evaluations.</CardContent></Card></div>
  </div>;
}

export function SettingsPage() {
  return <><PageHeading eyebrow="Workspace" title="Settings" description="Workspace configuration and policy controls for the local FinTrace demo."><Button asChild variant="outline" size="sm"><Link href="/investigations">Manage investigations</Link></Button></PageHeading><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Workspace details</CardTitle></CardHeader><CardContent className="space-y-4">{[["Workspace name", appConfig.workspaceName], ["Environment", appConfig.workspaceEnvironment], ["Currency", "Set per investigation"], ["Dataset mode", "Synthetic data or uploaded exports"]].map(row => <div key={row[0]} className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0"><span className="text-xs text-muted-foreground">{row[0]}</span><span className="text-xs font-semibold text-foreground">{row[1]}</span></div>)}</CardContent></Card><Card><CardHeader><CardTitle>Approval policy</CardTitle></CardHeader><CardContent className="space-y-4 text-xs"><p className="leading-5 text-muted-foreground">Financial actions remain gated by the deterministic control policy. Evidence investigation is read-only and cannot authorize or mutate a financial state.</p>{[["Low exposure", "Finance Manager"], ["Medium exposure", "Controller"], ["High exposure", "Controller + secondary approval"]].map(row => <div key={row[0]} className="flex items-center justify-between border-b border-border pb-3 last:border-0 last:pb-0"><span className="font-mono text-xs text-muted-foreground">{row[0]}</span><span className="text-xs font-semibold text-foreground">{row[1]}</span></div>)}</CardContent></Card></div></>;
}
