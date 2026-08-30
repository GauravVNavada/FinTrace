"use client";

import * as React from "react";
import { AlertCircle, CircleAlert, Loader2, ShieldCheck } from "lucide-react";
import { Badge, Button, Card, CardContent } from "@fintrace/ui";
import { patterns as demoPatterns, formatCurrency } from "../lib/data";
import { fetchPatterns } from "../lib/api-client";
import type { ApiPattern, Pattern } from "../lib/types";
import { PageHeading } from "./dashboard";
import { SeverityBadge } from "./status-badge";

function toViewModel(item: ApiPattern | Pattern): Pattern {
  if ("pattern_id" in item) {
    return {
      id: item.pattern_id,
      title: item.title,
      description: item.observation,
      incidents: item.occurrence_count,
      exposure: Number(item.associated_exposure),
      location: item.location,
      control: item.prevention_recommendation,
      severity: item.severity
    };
  }
  return item;
}

export function PatternsPage() {
  const [items, setItems] = React.useState<Pattern[]>(demoPatterns);
  const [loading, setLoading] = React.useState(true);
  const [apiUnavailable, setApiUnavailable] = React.useState(false);

  React.useEffect(() => {
    fetchPatterns()
      .then(result => setItems(result.map(toViewModel)))
      .catch(() => setApiUnavailable(true))
      .finally(() => setLoading(false));
  }, []);

  return <>
    <PageHeading eyebrow="Patterns" title="Recurring operational signals" description="Clusters of related exceptions can point to a control gap. They are signals for review, not proof of causation.">
      <Button variant="outline" size="sm">Export patterns</Button>
    </PageHeading>
    {apiUnavailable && <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertCircle className="h-4 w-4" />API unavailable — showing the typed demo snapshot.</div>}
    {loading && <div className="mb-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading deterministic pattern signals…</div>}
    <div className="mb-5 grid gap-4 sm:grid-cols-3"><Card><CardContent className="p-4"><div className="text-[11px] text-slate-400">Active patterns</div><div className="mt-2 text-xl font-bold text-slate-950">{items.length}</div><div className="mt-1 text-[11px] text-slate-500">Derived from canonical exceptions</div></CardContent></Card><Card><CardContent className="p-4"><div className="text-[11px] text-slate-400">Associated exposure</div><div className="mt-2 text-xl font-bold text-slate-950">{formatCurrency(items.reduce((total, item) => total + item.exposure, 0))}</div><div className="mt-1 text-[11px] text-slate-500">Across returned pattern members</div></CardContent></Card><Card><CardContent className="p-4"><div className="text-[11px] text-slate-400">Highest concentration</div><div className="mt-2 text-xl font-bold text-slate-950">{items[0]?.location ?? "—"}</div><div className="mt-1 text-[11px] text-slate-500">Sorted by incident count</div></CardContent></Card></div>
    {items.length === 0 ? <Card><CardContent className="py-16 text-center text-sm text-slate-500">No recurring patterns meet the minimum two-incident threshold.</CardContent></Card> : <div className="grid gap-4">{items.map(pattern => <Card key={pattern.id}><CardContent className="flex flex-col gap-5 p-5 md:flex-row md:items-center"><div className="flex min-w-0 flex-1 items-start gap-3"><div className="rounded-lg bg-rose-50 p-2.5 text-rose-600"><CircleAlert className="h-5 w-5" /></div><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[10px] text-slate-400">{pattern.id}</span><SeverityBadge severity={pattern.severity} /><h3 className="basis-full text-sm font-semibold text-slate-900 md:basis-auto">{pattern.title}</h3></div><p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">{pattern.description}</p></div></div><div className="grid grid-cols-3 gap-6 border-t border-slate-100 pt-4 text-xs md:border-l md:border-t-0 md:pl-6 md:pt-0"><div><div className="text-[10px] uppercase tracking-wide text-slate-400">Incidents</div><div className="mt-1 font-bold text-slate-800">{pattern.incidents}</div></div><div><div className="text-[10px] uppercase tracking-wide text-slate-400">Exposure</div><div className="mt-1 font-bold text-slate-800">{formatCurrency(pattern.exposure)}</div></div><div><div className="text-[10px] uppercase tracking-wide text-slate-400">Location</div><div className="mt-1 font-bold text-slate-800">{pattern.location}</div></div></div><div className="rounded-lg bg-slate-50 p-3 md:w-[270px]"><div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-400"><ShieldCheck className="h-3.5 w-3.5" />Suggested control</div><p className="mt-1.5 text-[11px] leading-4 text-slate-600">{pattern.control}</p><Badge className="mt-3 bg-white text-slate-500">Signal only</Badge></div></CardContent></Card>)}</div>}
  </>;
}
