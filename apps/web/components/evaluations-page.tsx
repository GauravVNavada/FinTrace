"use client";

import * as React from "react";
import { AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle } from "@fintrace/ui";
import { fetchLatestAIEvaluation, fetchLatestEvaluation, runAIEvaluation, runEvaluation } from "../lib/api-client";
import { appConfig } from "../lib/data";
import { PageHeading, ActionNotice } from "./dashboard";
import type { ApiAIEvaluation, ApiEvaluation } from "../lib/types";

export function EvaluationsPage() {
  const [reconciliation, setReconciliation] = React.useState<ApiEvaluation | null>(null);
  const [ai, setAi] = React.useState<ApiAIEvaluation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState<"reconciliation" | "ai" | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    Promise.all([fetchLatestEvaluation().catch(() => null), fetchLatestAIEvaluation().catch(() => null)]).then(([deterministic, liveAi]) => { setReconciliation(deterministic); setAi(liveAi); }).finally(() => setLoading(false));
  }, []);

  async function runDeterministic() {
    setRunning("reconciliation"); setError(null);
    try { setReconciliation(await runEvaluation({ orders: appConfig.benchmark.orders, seed: appConfig.benchmark.seed, anomaly_rate: appConfig.benchmark.anomalyRate }, `evaluation-${Date.now()}`)); } catch { setError("The deterministic evaluation could not be completed."); } finally { setRunning(null); }
  }

  async function runAi() {
    setRunning("ai"); setError(null);
    try { setAi(await runAIEvaluation(`ai-evaluation-${Date.now()}`)); } catch { setError("The AI evaluation is unavailable. Confirm a live provider is configured; no stub result is substituted."); } finally { setRunning(null); }
  }

  return <>
    <PageHeading eyebrow="Controls" title="Evaluation & reliability" description="Reconciliation and AI investigation are measured separately. AI metrics are persisted only from executed provider responses; unavailable providers do not silently become offline results."><div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => void runDeterministic()} disabled={running !== null}><ShieldCheck className="h-3.5 w-3.5" />{running === "reconciliation" ? "Running…" : "Run reconciliation"}</Button><Button size="sm" onClick={() => void runAi()} disabled={running !== null}><ShieldCheck className="h-3.5 w-3.5" />{running === "ai" ? "Running…" : "Run AI investigation"}</Button></div></PageHeading>
    <ActionNotice message={error} variant="destructive" />
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading latest evaluations…</div>}
    {!loading && !reconciliation && !ai && <Alert variant="warning" className="mb-4 flex items-center gap-2 text-xs"><AlertCircle className="h-4 w-4" />No evaluation results are persisted yet.</Alert>}
    <div className="grid gap-5 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>RECONCILIATION</CardTitle></CardHeader><CardContent>{reconciliation ? <div className="grid gap-4 text-xs sm:grid-cols-2"><Metric label="Match precision" value={`${reconciliation.report.match_precision}%`} detail="Correct safe matches" /><Metric label="Exception recall" value={`${reconciliation.report.exception_recall}%`} detail="Labeled breaks detected" /><Metric label="Match rate" value={`${reconciliation.report.match_rate}%`} detail={`${reconciliation.report.auto_reconciled} of ${reconciliation.report.lifecycles} lifecycles`} /><Metric label="Throughput" value={`${reconciliation.report.throughput_per_second}/s`} detail={`${reconciliation.report.unresolved_exceptions} unresolved`} /><div className="col-span-full rounded-md border border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">Seed {reconciliation.seed} · anomaly rate {reconciliation.anomaly_rate} · deterministic simulator labels</div></div> : <p className="text-xs text-muted-foreground">No deterministic benchmark run exists.</p>}</CardContent></Card>
      <Card><CardHeader><CardTitle>AI INVESTIGATION</CardTitle></CardHeader><CardContent>{ai ? <div className="grid gap-4 text-xs sm:grid-cols-2"><div className="col-span-full rounded-md border border-border bg-muted/20 p-3 text-[11px] font-semibold text-foreground">{ai.provider} · {ai.model} · live measured run</div><Metric label="Root-cause accuracy" value={`${ai.report.root_cause_accuracy}%`} detail="Resolvable labeled cases" /><Metric label="Resolution correctness" value={`${ai.report.resolution_correctness}%`} detail="Supported only when supportable" /><Metric label="Escalation accuracy" value={`${ai.report.escalation_accuracy}%`} detail="Insufficient evidence → review" /><Metric label="Citation validity" value={`${ai.report.evidence_citation_validity}%`} detail={`${ai.report.unsupported_claim_rate}% unsupported claims`} /><Metric label="Tool efficiency" value={`${ai.report.average_tool_calls} calls`} detail={`${ai.report.cases} independently authored cases`} /><Metric label="Latency" value={`p50 ${ai.report.p50_latency_ms} ms`} detail={`p95 ${ai.report.p95_latency_ms} ms`} /><Metric label="Provider failures" value={`${ai.report.provider_failure_rate}%`} detail={`Structured validity ${ai.report.structured_output_validity}%`} /></div> : <p className="text-xs text-muted-foreground">No AI benchmark run exists. Run it only with the configured live provider.</p>}</CardContent></Card>
    </div>
  </>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div><div className="mt-1 text-xl font-bold text-foreground">{value}</div><div className="mt-1 text-[11px] text-muted-foreground">{detail}</div></div>;
}
