"use client";

import * as React from "react";
import { AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import { Button, Card, CardContent, CardHeader, CardTitle } from "@fintrace/ui";
import { fetchLatestEvaluation } from "../lib/api-client";
import { PageHeading } from "./dashboard";
import type { ApiEvaluation } from "../lib/types";

export function EvaluationsPage() {
  const [evaluation, setEvaluation] = React.useState<ApiEvaluation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [unavailable, setUnavailable] = React.useState(false);

  React.useEffect(() => {
    fetchLatestEvaluation().then(setEvaluation).catch(() => setUnavailable(true)).finally(() => setLoading(false));
  }, []);

  const metrics = evaluation ? [
    ["Match precision", `${evaluation.report.match_precision}%`, "Correct safe matches"],
    ["Exception recall", `${evaluation.report.exception_recall}%`, "Actual breaks detected"],
    ["Match rate", `${evaluation.report.match_rate}%`, `${evaluation.report.auto_reconciled} of ${evaluation.report.lifecycles} lifecycles`],
    ["Unresolved", `${evaluation.report.unresolved_exceptions}`, "Requires human review"]
  ] : [];

  return <>
    <PageHeading eyebrow="Controls" title="Evaluation & reliability" description="Metrics are computed against hidden synthetic ground truth so the benchmark stays honest and reproducible."><Button variant="outline" size="sm">Run evaluation</Button></PageHeading>
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading latest evaluation…</div>}
    {unavailable && <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertCircle className="h-4 w-4" />No API evaluation is available yet. Run the documented benchmark to create one.</div>}
    {evaluation ? <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([label, value, detail]) => <Card key={label}><CardContent className="p-5"><div className="text-xs font-medium text-slate-500">{label}</div><div className="mt-3 text-[25px] font-bold text-slate-950">{value}</div><div className="mt-1 text-[11px] text-slate-400">{detail}</div></CardContent></Card>)}</div><Card className="mt-4"><CardHeader><CardTitle>Benchmark run</CardTitle></CardHeader><CardContent className="flex flex-wrap items-center gap-4 text-xs text-slate-500"><span>Seed <strong className="text-slate-800">{evaluation.seed}</strong></span><span>Anomaly rate <strong className="text-slate-800">{evaluation.anomaly_rate}</strong></span><span>Throughput <strong className="text-slate-800">{evaluation.report.throughput_per_second} records/s</strong></span><span className="flex items-center gap-1.5 rounded-md bg-emerald-50 px-2.5 py-1.5 font-medium text-emerald-800"><ShieldCheck className="h-4 w-4" />Synthetic benchmark only</span></CardContent></Card></> : <Card><CardContent className="py-16 text-center text-sm text-slate-500">Run an evaluation to populate this report.</CardContent></Card>}
  </>;
}
