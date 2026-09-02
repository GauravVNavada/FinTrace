"use client";

import * as React from "react";
import { AlertCircle, CircleAlert, Loader2 } from "lucide-react";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Select } from "@fintrace/ui";
import { fetchFinancialInvestigationPatterns, fetchFinancialInvestigations } from "../lib/api-client";
import { downloadCsv } from "../lib/export";
import type { ApiFinancialInvestigationPattern } from "../lib/types";
import { PageHeading } from "./dashboard";

export function PatternsPage() {
  const [items, setItems] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [investigations, setInvestigations] = React.useState<{ id: string; name: string; base_currency: string }[]>([]);
  const [currency, setCurrency] = React.useState("INR");
  const [investigationName, setInvestigationName] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [apiUnavailable, setApiUnavailable] = React.useState(false);
  const [exported, setExported] = React.useState(false);

  React.useEffect(() => {
    fetchFinancialInvestigations()
      .then(investigations => {
        setInvestigations(investigations);
        const requestedId = new URLSearchParams(window.location.search).get("investigation");
        const current = investigations.find(item => item.id === requestedId) ?? (investigations.length === 1 ? investigations[0] : null);
        if (!current) return;
        setCurrency(current.base_currency);
        setInvestigationName(current.name);
        return fetchFinancialInvestigationPatterns(current.id).then(setItems);
      })
      .catch(() => setApiUnavailable(true))
      .finally(() => setLoading(false));
  }, []);

  function formatMinor(value: number) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(value / 100);
  }

  function exportPatterns() {
    downloadCsv("fintrace-patterns.csv", ["Pattern ID", "Exception type", "Incidents", "Exposure", "Observation", "Order IDs"], items.map(pattern => [pattern.pattern_id, pattern.exception_type, pattern.occurrence_count, formatMinor(pattern.associated_exposure_minor), pattern.observation, pattern.member_order_ids.join(" ")]));
    setExported(true);
  }

  return <>
    <PageHeading eyebrow="Patterns" title="Recurring operational signals" description={investigationName ? `Investigation-scoped signals derived from ${investigationName}.` : "Select an investigation to view its persisted signals."}>
      {investigations.length > 1 && <Select aria-label="Select investigation" defaultValue={new URLSearchParams(typeof window === "undefined" ? "" : window.location.search).get("investigation") ?? ""} onChange={event => { if (event.target.value) window.location.href = `/patterns?investigation=${encodeURIComponent(event.target.value)}`; }} className="max-w-64"><option value="">Select investigation</option>{investigations.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>}
      <Button variant="outline" size="sm" onClick={exportPatterns} disabled={loading || items.length === 0}>Export patterns</Button>
    </PageHeading>
    {exported && <Alert variant="info" className="mb-4 text-xs" aria-live="polite">Patterns downloaded as CSV.</Alert>}
    {apiUnavailable && <Alert variant="destructive" className="mb-4 flex items-center gap-2 text-xs"><AlertCircle className="h-4 w-4" />The pattern API is unavailable. No stale snapshot has been substituted.</Alert>}
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading deterministic pattern signals…</div>}
    {!loading && !apiUnavailable && !investigationName && <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">{investigations.length > 1 ? "Choose an investigation above to view its patterns." : "Create an investigation and complete a reconciliation run before patterns can be derived."}</CardContent></Card>}
    {!loading && !apiUnavailable && investigationName && <div className="mb-5 grid gap-4 sm:grid-cols-3"><Card><CardContent className="p-4"><div className="text-[11px] text-muted-foreground">Active patterns</div><div className="mt-2 text-xl font-bold text-foreground">{items.length}</div><div className="mt-1 text-[11px] text-muted-foreground">Derived from canonical exceptions</div></CardContent></Card><Card><CardContent className="p-4"><div className="text-[11px] text-muted-foreground">Associated exposure</div><div className="mt-2 text-xl font-bold text-foreground">{formatMinor(items.reduce((total, item) => total + item.associated_exposure_minor, 0))}</div><div className="mt-1 text-[11px] text-muted-foreground">Across returned pattern members</div></CardContent></Card><Card><CardContent className="p-4"><div className="text-[11px] text-muted-foreground">Highest concentration</div><div className="mt-2 text-xl font-bold text-foreground">{items[0]?.exception_type ?? "—"}</div><div className="mt-1 text-[11px] text-muted-foreground">Sorted by occurrence count</div></CardContent></Card></div>}
    {!loading && !apiUnavailable && investigationName && items.length === 0 ? <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">No recurring patterns meet the minimum two-incident threshold.</CardContent></Card> : !loading && !apiUnavailable && <div className="grid gap-4">{items.map(pattern => <Card key={pattern.pattern_id}><CardHeader><div className="flex items-center gap-3"><div className="rounded-lg bg-destructive/10 p-2.5 text-destructive"><CircleAlert className="h-5 w-5" /></div><div><CardTitle className="text-sm">{pattern.exception_type}</CardTitle><p className="mt-1 font-mono text-[10px] text-muted-foreground">{pattern.pattern_id}</p></div></div></CardHeader><CardContent><p className="text-xs leading-5 text-muted-foreground">{pattern.observation}</p><div className="mt-4 grid gap-4 border-t border-border pt-4 text-xs sm:grid-cols-3"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Incidents</div><div className="mt-1 font-bold text-foreground">{pattern.occurrence_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Exposure</div><div className="mt-1 font-bold text-foreground">{formatMinor(pattern.associated_exposure_minor)}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Order members</div><div className="mt-1 font-mono text-[10px] text-foreground">{pattern.member_order_ids.slice(0, 4).join(", ")}{pattern.member_order_ids.length > 4 ? " …" : ""}</div></div></div><div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-[11px] text-muted-foreground">Advisory signal only. The pattern does not establish causation or authorize a financial action.</div></CardContent></Card>)}</div>}
  </>;
}
