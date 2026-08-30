"use client";

import * as React from "react";
import { AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import { Button, Card, CardContent } from "@fintrace/ui";
import { fetchAuditEvents } from "../lib/api-client";
import type { ApiAuditEvent } from "../lib/types";
import { PageHeading } from "./dashboard";

export function AuditPage() {
  const [events, setEvents] = React.useState<ApiAuditEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [unavailable, setUnavailable] = React.useState(false);

  React.useEffect(() => {
    fetchAuditEvents().then(setEvents).catch(() => setUnavailable(true)).finally(() => setLoading(false));
  }, []);

  return <>
    <PageHeading eyebrow="Controls" title="Audit trail" description="Append-only activity across investigations, approvals, and policy-bound actions."><Button variant="outline" size="sm">Export log</Button></PageHeading>
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading organization-scoped events…</div>}
    {unavailable && <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertCircle className="h-4 w-4" />Audit API unavailable. No local event snapshot is substituted.</div>}
    <Card><CardContent className="p-0">{events.length === 0 && !loading && !unavailable ? <div className="py-16 text-center text-sm text-slate-500">No audit events are available for this organization.</div> : <div className="divide-y divide-slate-100">{events.map(event => <div key={event.event_id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center"><div className="flex items-center gap-3 sm:w-[220px]"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-500"><ShieldCheck className="h-3.5 w-3.5" /></div><span className="font-mono text-[10px] text-slate-400">{new Date(event.created_at).toLocaleTimeString()}</span></div><div className="flex-1"><div className="text-xs font-semibold text-slate-800">{event.action}</div><div className="mt-1 text-[11px] text-slate-400">{event.resource_id} · {event.actor_id}</div></div><span className="font-mono text-[10px] text-slate-400">{event.event_id}</span></div>)}</div>}</CardContent></Card>
  </>;
}
