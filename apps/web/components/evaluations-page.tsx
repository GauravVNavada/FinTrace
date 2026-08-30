"use client";

import * as React from "react";
import { AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle } from "@fintrace/ui";
import { fetchLatestEvaluation, runEvaluation } from "../lib/api-client";
import { appConfig } from "../lib/data";
import { PageHeading, ActionNotice } from "./dashboard";
import type { ApiEvaluation } from "../lib/types";

export function EvaluationsPage() {
  const [evaluation, setEvaluation] = React.useState<ApiEvaluation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [unavailable, setUnavailable] = React.useState(false);
  const [running, setRunning] = React.useState(false);
  const [runError, setRunError] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetchLatestEvaluation().then(setEvaluation).catch(() => setUnavailable(true)).finally(() => setLoading(false));
  }, []);

  async function runBenchmark() {
    setRunning(true); setRunError(null); setUnavailable(false);
    try { setEvaluation(await runEvaluation({ orders: appConfig.benchmark.orders, seed: appConfig.benchmark.seed, anomaly_rate: appConfig.benchmark.anomalyRate }, `evaluation-${Date.now()}`)); }
    catch { setRunError("The evaluation could not be completed. Check that the API is available and try again."); }
    finally { setRunning(false); }
  }

  const metrics = evaluation ? [
    ["Match precision", `${evaluation.report.match_precision}%`, "Correct safe matches"],
    ["Exception recall", `${evaluation.report.exception_recall}%`, "Actual breaks detected"],
    ["Match rate", `${evaluation.report.match_rate}%`, `${evaluation.report.auto_reconciled} of ${evaluation.report.lifecycles} lifecycles`],
    ["Unresolved", `${evaluation.report.unresolved_exceptions}`, "Requires human review"]
  ] : [];

  return <>
    <PageHeading eyebrow="Controls" title="Evaluation & reliability" description="Metrics are computed against hidden synthetic ground truth so the benchmark stays honest and reproducible."><Button variant="outline" size="sm" onClick={runBenchmark} disabled={running}><ShieldCheck className={running ? "h-3.5 w-3.5 animate-pulse" : "h-3.5 w-3.5"} />{running ? "Running…" : "Run evaluation"}</Button></PageHeading>
    <ActionNotice message={runError} variant="destructive" />
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading latest evaluation…</div>}
    {unavailable && <Alert variant="warning" className="mb-4 flex items-center gap-2 text-xs"><AlertCircle className="h-4 w-4" />No API evaluation is available yet. Run the documented benchmark to create one.</Alert>}
    {evaluation ? <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([label, value, detail]) => <Card key={label}><CardContent className="p-5"><div className="text-xs font-medium text-muted-foreground">{label}</div><div className="mt-3 text-[25px] font-bold text-foreground">{value}</div><div className="mt-1 text-[11px] text-muted-foreground">{detail}</div></CardContent></Card>)}</div><Card className="mt-4"><CardHeader><CardTitle>Benchmark run</CardTitle></CardHeader><CardContent className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground"><span>Seed <strong className="text-foreground">{evaluation.seed}</strong></span><span>Anomaly rate <strong className="text-foreground">{evaluation.anomaly_rate}</strong></span><span>Throughput <strong className="text-foreground">{evaluation.report.throughput_per_second} records/s</strong></span><span className="flex items-center gap-1.5 rounded-md bg-success/10 px-2.5 py-1.5 font-medium text-success"><ShieldCheck className="h-4 w-4" />Synthetic benchmark only</span></CardContent></Card></> : <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Run an evaluation to populate this report.</CardContent></Card>}
  </>;
}
