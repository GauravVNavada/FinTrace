"use client";

import * as React from "react";
import { AlertCircle, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { Alert, Button, Card, CardContent, EmptyState } from "@fintrace/ui";
import { ApiClientError, fetchAuditEvents } from "../lib/api-client";
import { downloadCsv } from "../lib/export";
import type { ApiAuditEvent } from "../lib/types";
import { PageHeading } from "./dashboard";

export function AuditPage() {
  const [events, setEvents] = React.useState<ApiAuditEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<ApiClientError | null>(null);
  const [exported, setExported] = React.useState(false);
  const [reloadToken, setReloadToken] = React.useState(0);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    fetchAuditEvents()
      .then(result => { if (active) { setEvents(result); setError(null); } })
      .catch(reason => { if (active) setError(reason instanceof ApiClientError ? reason : new ApiClientError(0, "The audit trail could not be loaded.", "UNKNOWN_ERROR")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reloadToken]);

  function exportLog() {
    downloadCsv("fintrace-audit-log.csv", ["Event ID", "Created at", "Action", "Resource", "Actor", "Correlation ID"], events.map(event => [event.event_id, event.created_at, event.action, event.resource_id, event.actor_id, event.correlation_id]));
    setExported(true);
  }

  return <>
    <PageHeading eyebrow="Controls" title="Audit trail" description="Append-only activity across investigations, approvals, and policy-bound actions."><Button variant="outline" size="sm" onClick={exportLog} disabled={loading || events.length === 0}>Export log</Button></PageHeading>
    {exported && <Alert variant="info" className="mb-4 text-xs" aria-live="polite">Audit log downloaded as CSV.</Alert>}
    {loading && <div role="status" className="mb-4 flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading organization-scoped events…</div>}
    {error?.status === 403 && <Alert variant="warning" className="mb-4 flex items-center gap-2 text-xs"><AlertCircle className="h-4 w-4" />Audit access is restricted for your role. Ask a Controller or Finance Manager to review the organization log.</Alert>}
    {error && error.status !== 403 && <Alert variant="destructive" className="mb-4 flex items-center justify-between gap-3 text-xs"><span>{error.message}</span><Button variant="outline" size="sm" onClick={() => setReloadToken(value => value + 1)}><RefreshCw className="h-3.5 w-3.5" />Retry</Button></Alert>}
    {!error && <Card><CardContent className="p-0">{events.length === 0 && !loading ? <EmptyState icon={<ShieldCheck className="h-5 w-5" />} eyebrow="Organization scoped" title="No audit events yet" description="Actions taken in this workspace will appear here with their actor, resource, and correlation identifiers." /> : <div className="divide-y divide-border">{events.map(event => <div key={event.event_id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center"><div className="flex items-center gap-3 sm:w-[220px]"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-muted-foreground"><ShieldCheck className="h-3.5 w-3.5" /></div><span className="font-mono text-[10px] text-muted-foreground">{new Date(event.created_at).toLocaleTimeString()}</span></div><div className="flex-1"><div className="text-xs font-semibold text-foreground">{event.action}</div><div className="mt-1 text-[11px] text-muted-foreground">{event.resource_id} · {event.actor_id}</div></div><span className="font-mono text-[10px] text-muted-foreground">{event.event_id}</span></div>)}</div>}</CardContent></Card>}
  </>;
}
