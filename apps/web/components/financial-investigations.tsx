"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, FileSpreadsheet, FileText, FolderSearch, Loader2, Plus, ShieldCheck, Sparkles, Trash2, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, FileInput, Input, Select, Textarea } from "@fintrace/ui";
import { analyzeSourceFile, ApiClientError, approveResolution, confirmSourceMappings, createFinancialInvestigation, decideRelationship, deleteSourceFile, discoverRelationships, editSourceMapping, fetchFinancialInvestigation, fetchFinancialInvestigationPatterns, fetchFinancialInvestigations, fetchLatestReconciliation, fetchProviderHealth, fetchReconciliationResults, fetchReconciliationInvestigation, fetchRelationships, fetchSourceAnalysis, fetchSourceFiles, fetchSourceMappings, fetchLifecycle, generateDemoData, getClientIdentity, investigateReconciliationResult, launchFlagshipDemo, normalizeDataset, rejectResolution, requestFinancialResolution, runInvestigationReconciliation, updateSourceClassification, uploadSourceFile } from "../lib/api-client";
import type { ApiFinancialInvestigation, ApiFinancialInvestigationPattern, ApiInvestigation, ApiLifecycleResponse, ApiProviderHealth, ApiReconciliationResult, ApiReconciliationRun, ApiRelationshipProposal, ApiResolutionRequest, ApiSourceAnalysis, ApiSourceFile, ApiSourceMapping, DemoDataRequest, ResolutionActionCode, SourceType } from "../lib/types";
import { PageHeading } from "./dashboard";

const allowedExtensions = [".csv", ".xlsx"];
function currentActor() {
  const identity = getClientIdentity();
  return { id: identity.actor_id, role: identity.role };
}

function displayStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, character => character.toUpperCase());
}

export function InvestigationStageNav({ investigationId }: { investigationId: string }) {
  const pathname = usePathname();
  const stages = [
    ["Overview", `/investigations/${investigationId}`],
    ["Sources", `/investigations/${investigationId}/sources`],
    ["Relationships", `/investigations/${investigationId}/relationships`],
    ["Reconciliation", `/investigations/${investigationId}#reconciliation`],
    ["Exceptions", `/investigations/${investigationId}#exceptions`],
    ["Audit Context", `/audit?resource_id=${encodeURIComponent(investigationId)}`],
  ] as const;
  return <nav aria-label="Investigation stages" className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-border bg-card p-1">{stages.map(([label, href]) => { const active = label === "Overview" ? pathname === stages[0][1] : !href.includes("#") && pathname === href.split("?")[0]; return <Link key={label} href={href} aria-current={active ? "page" : undefined} className={`whitespace-nowrap rounded-md px-3 py-2 text-[11px] font-semibold transition-colors ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{label}</Link>; })}</nav>;
}

function LifecyclePreview({ lifecycle, exceptionType }: { lifecycle: ApiLifecycleResponse; exceptionType: string | null }) {
  const steps: Array<[string, Record<string, unknown> | undefined, string]> = [
    ["ORDER", lifecycle.order, "order_id"],
    ["PAYMENT", lifecycle.payments[0], "payment_id"],
    ["SETTLEMENT", lifecycle.settlements[0], "settlement_id"],
    ["INVOICE", lifecycle.invoices[0], "invoice_id"],
    ["REFUND", lifecycle.refunds[0], "refund_id"],
    ["INVENTORY", lifecycle.inventory_movements.find(item => item.movement_type === "RETURN") ?? lifecycle.inventory_movements[0], "movement_id"],
  ];
  return <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Financial lifecycle</div><div className="mt-3 grid gap-2 sm:grid-cols-6">{steps.map(([label, record, idKey], index) => { const missing = !record || (label === "SETTLEMENT" && exceptionType === "MISSING_SETTLEMENT") || (label === "INVENTORY" && exceptionType === "REFUND_WITHOUT_INVENTORY_RETURN" && !lifecycle.inventory_movements.some(item => item.movement_type === "RETURN")); const id = record?.[idKey]; return <React.Fragment key={label}><div className={`rounded-md border p-2 ${missing ? "border-destructive/30 bg-destructive/5" : "border-border bg-card"}`}><div className="flex items-center justify-between gap-1"><span className="text-[10px] font-bold text-foreground">{label}</span><span className={`text-[9px] font-semibold ${missing ? "text-destructive" : "text-success"}`}>{missing ? "MISSING" : "PRESENT"}</span></div><div className="mt-2 truncate font-mono text-[9px] text-muted-foreground">{id ? String(id) : "Expected record not found"}</div></div>{index < steps.length - 1 && <div className="hidden items-center justify-center text-muted-foreground sm:flex">↓</div>}</React.Fragment>; })}</div><p className="mt-3 text-[11px] text-muted-foreground">Expand the exception detail for source file, source row, identifier, timestamp, and amount/status lineage.</p></div>;
}

function InvestigationStory({ investigation }: { investigation: ApiInvestigation }) {
  const supporting = investigation.supporting_evidence.filter(item => item.verified !== false);
  const contradictory = investigation.contradictory_evidence.filter(item => item.verified !== false);
  const missing = investigation.missing_evidence.length;
  const unresolved = investigation.status === "UNRESOLVED";
  return <div className="mt-4 space-y-3 rounded-lg border border-border p-4"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">AI investigation</div><div className="rounded-md border border-border bg-muted/20 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Provider / status / duration</div><div className="mt-1 text-xs font-semibold text-foreground">{investigation.provider} · {investigation.model} · {investigation.status} · {investigation.latency_ms} ms</div></div><div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Evidence requests</div><div className="mt-2 space-y-2">{investigation.tool_calls.map(call => <div key={`${call.sequence_no}-${call.name}`} className="rounded-md border border-border bg-card p-2 text-[11px]"><div className="font-mono font-semibold text-foreground">{call.sequence_no}. {call.name}</div><div className="mt-1 text-muted-foreground">{call.result_summary}</div></div>)}</div></div>{unresolved ? <div className="rounded-md border border-warning/40 bg-warning/10 p-3"><div className="text-sm font-bold text-warning">Cannot safely resolve</div><p className="mt-1 text-xs leading-5 text-muted-foreground">{investigation.summary}</p><div className="mt-2 text-[11px] text-muted-foreground">Missing evidence: {investigation.missing_evidence.join("; ") || "Additional corroboration is required."}</div><div className="mt-2 text-[11px] font-semibold text-foreground">Human review required</div></div> : <div className="rounded-md border border-success/30 bg-success/5 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-success">Root cause</div><div className="mt-1 text-sm font-bold text-foreground">{investigation.root_cause_code ?? "Structured conclusion"}</div><p className="mt-1 text-xs leading-5 text-muted-foreground">{investigation.summary}</p></div>}<div><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Verified evidence</div><div className="mt-2 grid gap-2 sm:grid-cols-4"><div className="rounded-md bg-success/10 p-2"><div className="text-[10px] text-muted-foreground">Supporting</div><div className="text-sm font-bold text-foreground">{supporting.length}</div></div><div className="rounded-md bg-warning/10 p-2"><div className="text-[10px] text-muted-foreground">Contradictory</div><div className="text-sm font-bold text-foreground">{contradictory.length}</div></div><div className="rounded-md bg-muted p-2"><div className="text-[10px] text-muted-foreground">Missing</div><div className="text-sm font-bold text-foreground">{missing}</div></div><div className="rounded-md bg-destructive/10 p-2"><div className="text-[10px] text-muted-foreground">Rejected claims</div><div className="text-sm font-bold text-foreground">{investigation.rejected_evidence.length}</div></div></div></div><div className="rounded-md border border-info/30 bg-info/5 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-info">Recommendation</div><div className="mt-1 text-xs font-semibold text-foreground">{investigation.recommended_action_code ?? "Request manual review"}</div><div className="mt-2 text-[11px] text-muted-foreground">Human control: {investigation.requires_human_review ? "Controller review required" : "No automatic financial action"}</div></div><div className="text-[10px] text-muted-foreground">AI stopped after {investigation.tool_calls.length} bounded tool call{investigation.tool_calls.length === 1 ? "" : "s"}. Hidden chain-of-thought is not displayed.</div></div>;
}

function requestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value)) : "Not set";
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, character => character.toUpperCase());
}

function errorMessage(error: unknown) {
  if (error instanceof ApiClientError) return error.message;
  return "The request could not be completed. Check that the API is running and try again.";
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "FAILED" ? "destructive" : status === "RECONCILED" || status === "READY" ? "default" : "outline";
  return <Badge variant={tone}>{statusLabel(status)}</Badge>;
}

function reviewActionFor(exceptionType: string | null): ResolutionActionCode {
  if (exceptionType === "REFUND_WITHOUT_INVENTORY_RETURN") return "REQUEST_INVENTORY_VERIFICATION";
  if (exceptionType === "ERP_AMOUNT_MISMATCH" || exceptionType === "ERP_INVOICE_MISSING") return "REQUEST_ERP_INVOICE_CORRECTION";
  if (exceptionType === "MISSING_SETTLEMENT" || exceptionType === "SETTLEMENT_FEE_VARIANCE") return "REQUEST_SETTLEMENT_REVIEW";
  if (exceptionType === "DUPLICATE_PAYMENT" || exceptionType === "AMBIGUOUS_ASSOCIATION") return "REQUEST_PAYMENT_REVIEW";
  return "REQUEST_REFUND_REVIEW";
}

export function FinancialInvestigationsPage() {
  const [items, setItems] = React.useState<ApiFinancialInvestigation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetchFinancialInvestigations().then(setItems).catch(error => setError(errorMessage(error))).finally(() => setLoading(false));
  }, []);

  const [launching, setLaunching] = React.useState(false);
  const [launchError, setLaunchError] = React.useState<string | null>(null);
  async function launchDemo() {
    setLaunching(true); setLaunchError(null);
    try { const prepared = await launchFlagshipDemo(requestId()); window.location.href = `/?investigation=${encodeURIComponent(prepared.id)}`; }
    catch (error) { setLaunchError(errorMessage(error)); setLaunching(false); }
  }

  return <>
    <PageHeading eyebrow="Financial investigations" title="Start with your financial data" description="Create a controlled investigation workspace for source files, mappings, relationships, and reconciliation outcomes.">
      <Button variant="outline" size="sm" onClick={() => void launchDemo()} disabled={launching}>{launching ? "Preparing flagship demo…" : "Launch Flagship Demo"}</Button>
      <Button asChild size="sm"><Link href="/investigations/new"><Plus className="h-3.5 w-3.5" />New investigation</Link></Button>
    </PageHeading>
    {launchError && <Alert variant="destructive" className="mb-5"><AlertTitle>Flagship demo could not be prepared</AlertTitle><AlertDescription>{launchError}</AlertDescription></Alert>}
    {error && <Alert variant="destructive" className="mb-5"><AlertTitle>Unable to load investigations</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {loading && <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation workspaces…</div>}
    {!loading && !error && items.length === 0 && <Card><CardContent className="flex flex-col items-center px-6 py-16 text-center"><div className="rounded-full bg-primary/10 p-3 text-primary"><FolderSearch className="h-6 w-6" /></div><h2 className="mt-4 text-base font-semibold text-foreground">No investigations yet</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Create an investigation, then upload the exports you want FinTrace to understand. Your source files remain scoped to this workspace.</p><Button asChild className="mt-5" size="sm"><Link href="/investigations/new">Create your first investigation</Link></Button></CardContent></Card>}
    {!loading && !error && items.length > 0 && <div className="grid gap-4">{items.map(item => <Card key={item.id}><CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center"><div className="flex min-w-0 flex-1 items-start gap-3"><div className="rounded-lg bg-primary/10 p-2.5 text-primary"><FolderSearch className="h-5 w-5" /></div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[10px] text-muted-foreground">{item.id}</span><StatusBadge status={item.status} /></div><h2 className="mt-1 truncate text-sm font-semibold text-foreground">{item.name}</h2><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description || "No description provided."}</p></div></div><div className="grid grid-cols-3 gap-5 border-t border-border pt-4 text-xs md:border-l md:border-t-0 md:pl-5 md:pt-0"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Period</div><div className="mt-1 font-medium text-foreground">{formatDate(item.period_start)}</div><div className="text-muted-foreground">to {formatDate(item.period_end)}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Sources</div><div className="mt-1 font-bold text-foreground">{item.source_file_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Currency</div><div className="mt-1 font-bold text-foreground">{item.base_currency}</div></div></div><Button asChild variant="outline" size="sm"><Link href={`/investigations/${item.id}`}>Open <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card>)}</div>}
  </>;
}

export function NewFinancialInvestigationPage() {
  const router = useRouter();
  const [form, setForm] = React.useState({ name: "", description: "", period_start: "", period_end: "", base_currency: "INR" });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    const submittedForm = {
      ...form,
      period_start: event.currentTarget.querySelector<HTMLInputElement>("#period-start")?.value || form.period_start,
      period_end: event.currentTarget.querySelector<HTMLInputElement>("#period-end")?.value || form.period_end,
    };
    try {
      const result = await createFinancialInvestigation({ ...submittedForm, description: submittedForm.description || undefined, period_start: submittedForm.period_start || undefined, period_end: submittedForm.period_end || undefined }, requestId());
      router.push(`/investigations/${result.id}/sources`);
    } catch (submitError) {
      setError(errorMessage(submitError));
      setSaving(false);
    }
  }

  return <>
    <div className="mb-5"><Link href="/investigations" className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Back to investigations</Link></div>
    <PageHeading eyebrow="New workspace" title="Create a financial investigation" description="Give this investigation a clear scope. You can add source exports immediately after it is created." />
    {error && <Alert variant="destructive" className="mb-5"><AlertTitle>Investigation was not created</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
     <Card className="max-w-3xl"><CardHeader><CardTitle>Investigation details</CardTitle><CardDescription>These details become the audit and data-lineage boundary for the investigation.</CardDescription></CardHeader><CardContent><form onSubmit={submit} className="space-y-5"><div><label htmlFor="investigation-name" className="text-xs font-semibold text-foreground">Name</label><Input id="investigation-name" required minLength={1} maxLength={200} className="mt-2" placeholder="e.g. August 2026 marketplace close" value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} /></div><div><label htmlFor="investigation-description" className="text-xs font-semibold text-foreground">Description <span className="font-normal text-muted-foreground">(optional)</span></label><Textarea id="investigation-description" maxLength={2000} rows={4} className="mt-2" placeholder="What close, process, or financial question are you investigating?" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} /></div><div className="grid gap-4 sm:grid-cols-3"><div><label htmlFor="period-start" className="text-xs font-semibold text-foreground">Period start</label><Input id="period-start" type="date" required className="mt-2" value={form.period_start} onChange={event => setForm(current => ({ ...current, period_start: event.target.value }))} /></div><div><label htmlFor="period-end" className="text-xs font-semibold text-foreground">Period end</label><Input id="period-end" type="date" required className="mt-2" value={form.period_end} onChange={event => setForm(current => ({ ...current, period_end: event.target.value }))} /></div><div><label htmlFor="base-currency" className="text-xs font-semibold text-foreground">Base currency</label><Select id="base-currency" className="mt-2" value={form.base_currency} onChange={event => setForm(current => ({ ...current, base_currency: event.target.value }))}><option value="INR">INR · Indian Rupee</option><option value="USD">USD · US Dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound Sterling</option></Select></div></div><div className="flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:justify-end"><Button asChild variant="outline" size="sm"><Link href="/investigations">Cancel</Link></Button><Button type="submit" size="sm" disabled={saving}>{saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{saving ? "Creating…" : "Create and add sources"}</Button></div></form></CardContent></Card>
  </>;
}

function SourceFileRow({ investigationId, source, onDeleted, onChanged }: { investigationId: string; source: ApiSourceFile; onDeleted: (sourceId: string) => void; onChanged: (source: ApiSourceFile) => void }) {
  const [deleting, setDeleting] = React.useState(false);
  const [analyzing, setAnalyzing] = React.useState(false);
  const [expanded, setExpanded] = React.useState(false);
  const [analysis, setAnalysis] = React.useState<ApiSourceAnalysis | null>(null);
  const [mappings, setMappings] = React.useState<ApiSourceMapping[]>([]);
  const [message, setMessage] = React.useState<string | null>(null);
  async function remove() {
    if (!window.confirm(`Remove ${source.original_filename} from this investigation?`)) return;
    setDeleting(true);
    try { await deleteSourceFile(investigationId, source.id); onDeleted(source.id); } catch { setDeleting(false); }
  }
  async function review() {
    setMessage(null); setAnalyzing(true); setExpanded(true);
    try {
      const [loadedAnalysis] = await Promise.all([source.status === "UPLOADED" ? analyzeSourceFile(investigationId, source.id) : fetchSourceAnalysis(investigationId, source.id), source.status === "UPLOADED" ? Promise.resolve([] as ApiSourceMapping[]) : fetchSourceMappings(investigationId, source.id)]);
      setAnalysis(loadedAnalysis);
      setMappings(await fetchSourceMappings(investigationId, source.id));
      onChanged({ ...source, status: source.status === "READY" ? "READY" : "MAPPING_REQUIRED", detected_source_type: loadedAnalysis.source_type, detection_confidence: loadedAnalysis.classification_confidence });
    } catch (reviewError) { setMessage(errorMessage(reviewError)); }
    finally { setAnalyzing(false); }
  }
  return <div className="border-b border-border py-4 last:border-b-0"><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="flex min-w-0 flex-1 items-center gap-3"><div className="rounded-md bg-muted p-2 text-muted-foreground">{source.original_filename.toLowerCase().endsWith(".xlsx") ? <FileSpreadsheet className="h-4 w-4" /> : <FileText className="h-4 w-4" />}</div><div className="min-w-0"><div className="truncate text-xs font-semibold text-foreground">{source.original_filename}</div><div className="mt-1 text-[11px] text-muted-foreground">{formatBytes(source.size_bytes)} · {source.row_count.toLocaleString()} rows · {source.column_count} columns</div></div></div><div className="flex items-center gap-2"><StatusBadge status={source.status} /><Button variant="outline" size="sm" onClick={() => { setExpanded(!expanded); if (!expanded && !analysis) void review(); }}>{analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{analysis ? (expanded ? "Hide mapping" : "Review mapping") : "Analyze source"}</Button><Button variant="ghost" size="icon" aria-label={`Remove ${source.original_filename}`} onClick={remove} disabled={deleting}>{deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}</Button></div></div>{message && <Alert variant="destructive" className="mt-3"><AlertDescription>{message}</AlertDescription></Alert>}{expanded && analysis && <MappingReview investigationId={investigationId} source={source} analysis={analysis} mappings={mappings} onMappings={setMappings} onChanged={onChanged} />}</div>;
}

function MappingReview({ investigationId, source, analysis, mappings, onMappings, onChanged }: { investigationId: string; source: ApiSourceFile; analysis: ApiSourceAnalysis; mappings: ApiSourceMapping[]; onMappings: React.Dispatch<React.SetStateAction<ApiSourceMapping[]>>; onChanged: (source: ApiSourceFile) => void }) {
  const [saving, setSaving] = React.useState<string | null>(null);
  const [confirming, setConfirming] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  async function save(mapping: ApiSourceMapping, canonical_field: string, ignored: boolean) {
    setSaving(mapping.id); setError(null);
    try { const updated = await editSourceMapping(investigationId, source.id, mapping.id, { canonical_field: canonical_field || null, ignored }); onMappings(current => current.map(item => item.id === updated.id ? updated : item)); }
    catch (saveError) { setError(errorMessage(saveError)); } finally { setSaving(null); }
  }
  async function confirm() {
    setConfirming(true); setError(null); setNotice(null);
    try { await confirmSourceMappings(investigationId, source.id); onMappings(current => current.map(item => ({ ...item, status: "CONFIRMED" }))); onChanged({ ...source, status: "READY" }); setNotice("Required mappings confirmed. Relationship review is the next controlled stage."); }
    catch (confirmError) { setError(errorMessage(confirmError)); } finally { setConfirming(false); }
  }
  async function classify(event: React.ChangeEvent<HTMLSelectElement>) {
    setSaving("classification"); setError(null);
    try { const updated = await updateSourceClassification(investigationId, source.id, event.target.value as SourceType); onChanged({ ...source, detected_source_type: updated.source_type, detection_confidence: updated.classification_confidence, status: "MAPPING_REQUIRED" }); }
    catch (classifyError) { setError(errorMessage(classifyError)); } finally { setSaving(null); }
  }
  const missing = mappings.filter(mapping => mapping.required && (!mapping.canonical_field || mapping.ignored));
  return <div className="mt-4 rounded-lg border border-border bg-muted/20 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-xs font-semibold text-foreground">Source analysis</div><p className="mt-1 text-[11px] leading-5 text-muted-foreground">{analysis.reasoning_summary}</p><div className="mt-2 flex flex-wrap gap-2 text-[10px] font-semibold"><Badge variant={analysis.provider_status === "AI_PROVIDER" ? "default" : analysis.provider_status === "AI_PROVIDER_UNAVAILABLE" ? "destructive" : "outline"}>{analysis.provider_status === "AI_PROVIDER" ? "Live provider" : analysis.provider_status === "AI_PROVIDER_UNAVAILABLE" ? "AI provider unavailable" : "Offline deterministic analysis · NOT AI"}</Badge><span className="rounded border border-border px-2 py-1">{analysis.provider} · {analysis.model}</span><span className="rounded border border-border px-2 py-1">{Math.round(analysis.classification_confidence * 100)}% proposal confidence</span></div><p className="mt-2 text-[10px] text-muted-foreground">Only column names, inferred types, row count, basic statistics, and a bounded sample are sent to the configured provider.</p></div><label className="text-[11px] font-semibold text-foreground">Classification<Select className="mt-1 min-w-44" value={analysis.source_type} onChange={classify} disabled={saving === "classification"}><option value="UNKNOWN">Unknown</option>{["SALES", "ORDERS", "PAYMENTS", "SETTLEMENTS", "REFUNDS", "INVOICES", "INVENTORY_MOVEMENTS", "EMPLOYEE_ACTIONS"].map(type => <option key={type} value={type}>{statusLabel(type)}</option>)}</Select></label></div><div className="mt-4 space-y-2">{mappings.map(mapping => <div key={mapping.id} className="grid gap-2 rounded-md border border-border bg-background p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-center"><div><div className="text-xs font-medium text-foreground">{mapping.source_column}{mapping.required && <span className="ml-1 text-destructive">Required</span>}</div><div className="text-[10px] text-muted-foreground">{mapping.inferred_type} · {Math.round(mapping.confidence * 100)}% proposal</div></div><Input aria-label={`Canonical field for ${mapping.source_column}`} value={mapping.canonical_field ?? ""} onChange={event => onMappings(current => current.map(item => item.id === mapping.id ? { ...item, canonical_field: event.target.value, ignored: event.target.value === "" } : item))} onBlur={event => void save(mapping, event.target.value, event.target.value === "")} disabled={saving === mapping.id} placeholder="canonical field" /><Button variant="outline" size="sm" onClick={() => void save(mapping, "", true)} disabled={saving === mapping.id}>Ignore</Button></div>)}</div>{missing.length > 0 && <p className="mt-3 text-[11px] text-warning">{missing.length} required mapping(s) still need a canonical field.</p>}{error && <Alert variant="destructive" className="mt-3"><AlertDescription>{error}</AlertDescription></Alert>}{notice && <Alert variant="info" className="mt-3"><AlertDescription>{notice}</AlertDescription></Alert>}<div className="mt-4 flex items-center justify-between">{source.status === "READY" ? <span className="text-[11px] font-semibold text-success">Required mappings confirmed. This source is ready for normalization.</span> : <><span className="text-[11px] text-muted-foreground">Confirmation is required before normalization.</span><Button size="sm" onClick={() => void confirm()} disabled={confirming || missing.length > 0}>{confirming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{confirming ? "Confirming…" : "Confirm mappings"}</Button></>}</div></div>;
}

export function RelationshipReview({ investigationId }: { investigationId: string }) {
  const [items, setItems] = React.useState<ApiRelationshipProposal[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchRelationships(investigationId).then(setItems).catch(() => undefined).finally(() => setLoading(false)); }, [investigationId]);
  async function discover() { setWorking(true); setError(null); try { setItems(await discoverRelationships(investigationId)); } catch (discoverError) { setError(errorMessage(discoverError)); } finally { setWorking(false); } }
  async function decide(item: ApiRelationshipProposal, status: "ACCEPTED" | "REJECTED") { setWorking(true); try { const updated = await decideRelationship(investigationId, item.id, status); setItems(current => current.map(candidate => candidate.id === updated.id ? updated : candidate)); } catch (decisionError) { setError(errorMessage(decisionError)); } finally { setWorking(false); } }
  return <Card className="mt-4"><CardHeader><CardTitle>Relationship review</CardTitle><CardDescription>FinTrace calculates overlap, cardinality, duplicates, type compatibility, temporal consistency, and amount agreement from the uploaded rows. AI does not calculate these metrics.</CardDescription></CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{loading ? <div role="status" className="text-xs text-muted-foreground">Loading relationship proposals…</div> : items.length === 0 ? <div className="flex flex-col items-start gap-3"><p className="text-xs text-muted-foreground">No proposals yet. Discover relationships after confirming mappings.</p><Button size="sm" onClick={() => void discover()} disabled={working}>Discover relationships</Button></div> : <div className="space-y-3">{items.map(item => <div key={item.id} className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-foreground">{item.source_file_id} <span className="text-muted-foreground">to</span> {item.target_source_file_id}<Badge variant={item.confidence_label === "HIGH" ? "default" : "outline"}>{item.confidence_label}</Badge></div><p className="mt-1 text-[11px] text-muted-foreground">{item.evidence_summary} Join: {item.join_fields.join(", ")} · {Math.round(item.confidence * 100)}%</p><div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-muted-foreground sm:grid-cols-4"><span>Overlap {item.value_overlap_percent.toFixed(1)}%</span><span>Cardinality {item.cardinality}</span><span>Duplicates {item.duplicate_key_rate_percent.toFixed(1)}%</span><span>Types {item.type_compatibility}</span>{item.temporal_consistency_percent !== null && <span>Temporal {item.temporal_consistency_percent.toFixed(1)}%</span>}{item.amount_agreement_percent !== null && <span>Amount {item.amount_agreement_percent.toFixed(1)}%</span>}</div></div><div className="flex items-center gap-2"><StatusBadge status={item.status} />{item.status === "PROPOSED" && <><Button variant="outline" size="sm" onClick={() => void decide(item, "REJECTED")} disabled={working}>Reject</Button><Button size="sm" onClick={() => void decide(item, "ACCEPTED")} disabled={working}>Accept</Button></>}</div></div>)}</div>}</CardContent></Card>;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ReconciliationRunPanelSummary({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [providerHealth, setProviderHealth] = React.useState<ApiProviderHealth | null>(null);
  const load = React.useCallback(() => fetchLatestReconciliation(investigationId).then(loaded => { setRun(loaded); return fetchReconciliationResults(investigationId, loaded.id); }).then(loaded => { setResults(loaded); setSelectedId(current => current ?? loaded.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null); }).catch(() => undefined), [investigationId]);
  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => { fetchProviderHealth().then(setProviderHealth).catch(() => setProviderHealth({ status: "UNAVAILABLE", provider: "unknown", model: "unknown", configured: false, latency_ms: 0, error_category: "health_check_failed", retryable: true, detail: "Provider health could not be checked.", overall_status: "UNAVAILABLE", active_provider: null, providers: [] })); }, []);
  const selected = results.find(item => item.id === selectedId) ?? null;
  async function inspect(result: ApiReconciliationResult) { if (!run) return; setSelectedId(result.id); setWorking(true); setError(null); try { setInvestigation(await fetchReconciliationInvestigation(investigationId, run.id, result.id)); } catch { setInvestigation(null); } finally { setWorking(false); } }
  async function investigate() { if (!run || !selected) return; setWorking(true); setError(null); try { setInvestigation(await investigateReconciliationResult(investigationId, run.id, selected.id)); } catch (cause) { setError(errorMessage(cause)); } finally { setWorking(false); } }
  return <Card className="mt-4"><CardHeader><CardTitle>Deterministic reconciliation</CardTitle><CardDescription>The immutable dataset is reconciled by code. AI only investigates the exceptions after this run, and every provider claim is verified before it can be supported.</CardDescription>{providerHealth && <ProviderHealthSummary health={providerHealth} />}</CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{run ? <><div className="grid gap-3 sm:grid-cols-5"><MetricCell label="Lifecycles" value={run.lifecycle_count.toLocaleString()} /><MetricCell label="Reconciled" value={run.reconciled_count.toLocaleString()} /><MetricCell label="Variance" value={results.filter(item => item.status === "RECONCILED_WITH_VARIANCE").length.toLocaleString()} /><MetricCell label="Exceptions" value={(run.exception_count + run.ambiguous_count).toLocaleString()} /><MetricCell label="Potential exposure" value={(run.open_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })} /></div><div className="mt-3 rounded-md border border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">Input accounting: {run.records_consumed.toLocaleString()} consumed / {run.records_expected.toLocaleString()} expected · {run.status}{run.failure_reason ? ` · ${run.failure_reason}` : ""}</div></> : <p className="text-xs text-muted-foreground">No reconciliation run exists for this investigation yet.</p>}{results.length > 0 && <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]"><div className="max-h-80 space-y-2 overflow-auto pr-1">{results.filter(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS").map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className={`w-full rounded-md border p-3 text-left text-xs ${selected?.id === item.id ? "border-primary bg-primary/5" : "border-border bg-muted/20"}`}><div className="flex items-center justify-between gap-2"><span className="font-semibold text-foreground">{item.order_id}</span><StatusBadge status={item.status} /></div><div className="mt-1 text-[11px] text-muted-foreground">{item.exception_type ?? "AMBIGUOUS"} · {item.exposure_category} · associated {item.exposure_minor.toLocaleString()} minor units</div></Button>)}</div>{selected && <div className="rounded-md border border-border p-4 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><div><div className="font-semibold text-foreground">AI INVESTIGATION · {selected.exception_type ?? "AMBIGUOUS"}</div><div className="mt-1 text-[11px] text-muted-foreground">Lifecycle {selected.order_id} · deterministic findings: {selected.findings.map(item => item.code).join(", ")}</div></div><Button size="sm" onClick={() => void investigate()} disabled={working}>{working ? "Investigating…" : investigation ? "Re-run investigation" : "Investigate with AI"}</Button></div>{investigation ? <><div className="mt-3 rounded-md border border-border bg-muted/20 p-3 text-[11px] font-semibold text-foreground">{investigation.provider} · {investigation.model} · {investigation.status === "FAILED" ? "provider unavailable" : "completed"} · {investigation.latency_ms} ms</div><p className="mt-3 leading-5 text-muted-foreground">{investigation.summary}</p>{investigation.fallback_used && <div className="mt-2 rounded-md border border-warning/30 bg-warning/5 p-3 text-[11px] text-muted-foreground">{investigation.originally_requested_provider} unavailable · investigation completed with {investigation.actual_provider_used} fallback</div>}{investigation.status === "FAILED" && <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-[11px] text-muted-foreground">Provider failure: {investigation.provider_error_category ?? "unknown"} · retryable {investigation.provider_retryable ? "yes" : "no"} · stage {investigation.failure_stage ?? "unknown"} · iteration {investigation.failure_iteration ?? "n/a"}</div>}<div className="mt-3 grid gap-3 sm:grid-cols-3"><div><div className="text-[10px] uppercase text-muted-foreground">Root cause</div><div className="mt-1 font-semibold text-foreground">{investigation.root_cause_code ?? "UNRESOLVED"}</div></div><div><div className="text-[10px] uppercase text-muted-foreground">Evidence score</div><div className="mt-1 font-semibold text-foreground">{investigation.evidence_score}/100</div></div><div><div className="text-[10px] uppercase text-muted-foreground">Verifier</div><div className="mt-1 font-semibold text-foreground">{investigation.verifier_passed ? "Passed" : "Review required"}</div></div></div><EvidencePanel title="Supporting evidence" items={investigation.supporting_evidence} /><EvidencePanel title="Contradictory evidence" items={investigation.contradictory_evidence} /><div className="mt-3"><div className="font-semibold text-foreground">Missing evidence</div>{investigation.missing_evidence.length ? <ul className="mt-1 list-disc space-y-1 pl-4 text-muted-foreground">{investigation.missing_evidence.map(item => <li key={item}>{item}</li>)}</ul> : <div className="mt-1 text-muted-foreground">None recorded.</div>}</div>{investigation.rejected_evidence.length > 0 && <EvidencePanel title="Verification issues" items={investigation.rejected_evidence} />}{investigation.tool_calls.length > 0 && <div className="mt-3 border-t border-border pt-3"><div className="font-semibold text-foreground">Bounded tool trace</div><div className="mt-2 space-y-1 text-muted-foreground">{investigation.tool_calls.map(call => <div key={`${call.sequence_no}-${call.name}`}><span className="font-semibold text-foreground">{call.sequence_no}. {call.name}</span> · {call.result_summary} · {call.duration_ms} ms</div>)}</div></div>}</> : <p className="mt-6 text-center text-xs text-muted-foreground">Select an exception and run the bounded provider investigation.</p>}</div>}</div>}</CardContent></Card>;
}

function ProviderHealthSummary({ health }: { health: ApiProviderHealth }) {
  const tone = health.overall_status === "AVAILABLE" ? "border-success/30 bg-success/5" : health.overall_status === "DEGRADED" ? "border-warning/30 bg-warning/5" : "border-destructive/30 bg-destructive/5";
  return <div className={`mt-3 rounded-md border p-3 text-[11px] ${tone}`}><div className="font-semibold text-foreground">{health.overall_status === "AVAILABLE" ? "AI ready" : health.overall_status === "DEGRADED" ? "AI ready · fallback available" : "AI unavailable"}</div><div className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">{health.providers.map(item => <div key={`${item.provider}-${item.model}`}><span className="font-semibold text-foreground">{item.provider === "gemini" ? "Primary" : "Fallback"}</span> · {item.provider} · {item.model} · {item.status === "CONNECTED" ? "Connected" : item.status === "NOT_CONFIGURED" ? "Not configured" : `Unavailable${item.error_category ? ` · ${item.error_category}` : ""}`}</div>)}</div></div>;
}

function MetricCell({ label, value }: { label: string; value: string }) { return <div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div><div className="mt-1 text-lg font-bold text-foreground">{value}</div></div>; }
function EvidencePanel({ title, items }: { title: string; items: { source: string; record_id?: string | null; fact: string; verification_issue?: string | null }[] }) { return <div className="mt-3"><div className="font-semibold text-foreground">{title}</div>{items.length ? <div className="mt-1 space-y-1 text-muted-foreground">{items.map((item, index) => <div key={`${item.source}-${item.record_id ?? "missing"}-${index}`}>{item.source}{item.record_id ? ` · ${item.record_id}` : " · no record"} · {item.fact}{item.verification_issue ? ` · ${item.verification_issue}` : ""}</div>)}</div> : <div className="mt-1 text-muted-foreground">None recorded.</div>}</div>; }

function ReconciliationStory({ run, results, currency }: { run: ApiReconciliationRun; results: ApiReconciliationResult[]; currency: string }) {
  const count = (status: string) => results.filter(item => item.status === status).length;
  const categories = ["POTENTIAL_EXPOSURE", "TIMING_VARIANCE", "DATA_QUALITY", "CONTROL_RISK"];
  return <div className="rounded-lg border border-border p-4"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Control outcome distribution</div><div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">{[["Records processed", run.records_loaded], ["Lifecycles reconstructed", run.lifecycle_count], ["Reconciled", run.reconciled_count], ["Reconciled with variance", count("RECONCILED_WITH_VARIANCE")], ["Exceptions", run.exception_count], ["Ambiguous", run.ambiguous_count]].map(([label, value]) => <div key={label} className="rounded-md bg-muted/40 p-3"><div className="text-[10px] text-muted-foreground">{label}</div><div className="mt-1 text-lg font-bold text-foreground">{Number(value).toLocaleString()}</div></div>)}</div><div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground"><span>Requires review</span><Badge variant={run.exception_count + run.ambiguous_count > 0 ? "outline" : "default"}>{(run.exception_count + run.ambiguous_count).toLocaleString()}</Badge><span>·</span><span>Potential exposure {((run.open_exposure_minor ?? 0) / 100).toLocaleString("en-IN", { style: "currency", currency })}</span></div><div className="mt-4 border-t border-border pt-4"><div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Financial / control categories</div><div className="mt-2 grid gap-2 sm:grid-cols-4">{categories.map(category => <div key={category} className="rounded-md border border-border p-3"><div className="text-[10px] text-muted-foreground">{displayStatus(category)}</div><div className="mt-1 text-lg font-bold text-foreground">{results.filter(item => item.exposure_category === category).length}</div></div>)}</div></div></div>;
}

// Kept as a compatibility reference while the uploaded-investigation panel is the primary flow.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyReconciliationRunPanel({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [patterns, setPatterns] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [investigated, setInvestigated] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [reviewRequest, setReviewRequest] = React.useState<ApiResolutionRequest | null>(null);
  const [requestingReview, setRequestingReview] = React.useState(false);
  const [working, setWorking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchLatestReconciliation(investigationId).then(loaded => { setRun(loaded); return Promise.all([fetchReconciliationResults(investigationId, loaded.id), fetchFinancialInvestigationPatterns(investigationId)]); }).then(([loadedResults, loadedPatterns]) => { setResults(loadedResults); setPatterns(loadedPatterns); const existing = loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS"); return existing ? fetchReconciliationInvestigation(investigationId, existing.run_id, existing.id).then(loadedInvestigation => { setInvestigation(loadedInvestigation); setInvestigated(loadedInvestigation.status); }).catch(() => undefined) : undefined; }).catch(() => undefined); }, [investigationId]);
  async function reconcile() {
    setWorking(true); setError(null);
    try {
      const dataset = await normalizeDataset(investigationId);
      const completed = await runInvestigationReconciliation(investigationId, dataset.id);
      setRun(completed); const [loadedResults, loadedPatterns] = await Promise.all([fetchReconciliationResults(investigationId, completed.id), fetchFinancialInvestigationPatterns(investigationId)]); setResults(loadedResults); setPatterns(loadedPatterns);
    } catch (runError) { setError(errorMessage(runError)); } finally { setWorking(false); }
  }
  async function investigate() {
    const result = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
    if (!run || !result) return;
    setWorking(true); setError(null);
    try { const response = await investigateReconciliationResult(investigationId, run.id, result.id); setInvestigated(response.status); setInvestigation(response); }
    catch (investigateError) { setError(errorMessage(investigateError)); } finally { setWorking(false); }
  }
  async function requestReview() {
    const result = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
    if (!run || !result) return;
    setRequestingReview(true); setError(null);
    try { setReviewRequest(await requestFinancialResolution(investigationId, run.id, result.id, reviewActionFor(result.exception_type), requestId())); }
    catch (reviewError) { setError(errorMessage(reviewError)); }
    finally { setRequestingReview(false); }
  }
  const exception = results.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");
  return <Card className="mt-4"><CardHeader><CardTitle>Deterministic reconciliation</CardTitle><CardDescription>Normalize the confirmed sources into an immutable dataset, then run the deterministic lifecycle rules. No AI call changes this result.</CardDescription></CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{run ? <div className="grid gap-3 sm:grid-cols-4"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Lifecycles</div><div className="mt-1 text-xl font-bold text-foreground">{run.lifecycle_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Reconciled</div><div className="mt-1 text-xl font-bold text-foreground">{run.reconciled_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Exceptions</div><div className="mt-1 text-xl font-bold text-warning">{run.exception_count + run.ambiguous_count}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Exposure</div><div className="mt-1 text-xl font-bold text-foreground">{(run.open_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })}</div></div></div> : <p className="text-xs text-muted-foreground">No reconciliation run exists for this investigation yet.</p>}{patterns.length > 0 && <div className="mt-4 rounded-md border border-border bg-muted/20 p-3 text-xs"><div className="font-semibold text-foreground">Advisory recurring signals</div>{patterns.map(pattern => <div key={pattern.pattern_id} className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground"><span className="font-semibold text-foreground">{pattern.exception_type}</span><span>·</span><span>{pattern.occurrence_count} occurrences</span><span>·</span><span>{(pattern.associated_exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })} exposure</span></div>)}</div>}{exception && <div className="mt-4 flex flex-col gap-2 rounded-md border border-border bg-muted/20 p-3 text-xs sm:flex-row sm:items-center sm:justify-between"><span><span className="font-semibold text-foreground">{exception.order_id}</span> · {exception.exception_type ?? "Ambiguous result"} · requires bounded evidence review</span><div className="flex flex-wrap items-center gap-2"><Button variant="outline" size="sm" onClick={() => void investigate()} disabled={working || investigated !== null}>{investigated ? `Investigation ${investigated.toLowerCase()}` : "Investigate exception"}</Button><Button size="sm" onClick={() => void requestReview()} disabled={working || requestingReview || reviewRequest !== null}>{requestingReview ? "Requesting review…" : reviewRequest ? "Review requested" : "Request human review"}</Button></div></div>}{investigation && <div className="mt-4 rounded-md border border-border p-4 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-semibold text-foreground">Evidence investigation</div><StatusBadge status={investigation.status} /></div><p className="mt-2 leading-5 text-muted-foreground">{investigation.summary}</p>{investigation.status === "FAILED" && <Alert variant="destructive" className="mt-3"><AlertDescription>AI provider unavailable. Deterministic evidence remains available for manual review.</AlertDescription></Alert>}<div className="mt-3 grid gap-3 sm:grid-cols-3"><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Evidence score</div><div className="mt-1 font-bold text-foreground">{investigation.evidence_score}/100</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Root cause</div><div className="mt-1 font-semibold text-foreground">{investigation.root_cause_code ?? "Unresolved"}</div></div><div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Review</div><div className="mt-1 font-semibold text-foreground">{investigation.requires_human_review ? "Human review required" : "No review required"}</div></div></div>{investigation.tool_calls.length > 0 && <div className="mt-3 border-t border-border pt-3"><div className="font-semibold text-foreground">Read-only evidence trace</div><div className="mt-2 space-y-1 text-muted-foreground">{investigation.tool_calls.map(call => <div key={`${call.name}-${call.target}`} className="flex flex-wrap gap-x-2"><span className="font-medium text-foreground">{call.name}</span><span>{call.target}</span><span>· {call.status}</span><span>· {call.duration_ms} ms</span></div>)}</div></div>}</div>}{reviewRequest && <Alert variant="info" className="mt-4"><AlertTitle>Human review requested</AlertTitle><AlertDescription>{reviewRequest.action_code} is pending approval. The financial state has not been changed.</AlertDescription></Alert>}<Button className="mt-4" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{working ? "Processing…" : run ? "Run again" : "Normalize and reconcile"}</Button></CardContent></Card>;
}

export function ReconciliationRunPanel({ investigationId, currency }: { investigationId: string; currency: string }) {
  const [run, setRun] = React.useState<ApiReconciliationRun | null>(null);
  const [results, setResults] = React.useState<ApiReconciliationResult[]>([]);
  const [patterns, setPatterns] = React.useState<ApiFinancialInvestigationPattern[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [investigation, setInvestigation] = React.useState<ApiInvestigation | null>(null);
  const [lifecycle, setLifecycle] = React.useState<ApiLifecycleResponse | null>(null);
  const [reviewRequest, setReviewRequest] = React.useState<ApiResolutionRequest | null>(null);
  const [providerHealth, setProviderHealth] = React.useState<ApiProviderHealth | null>(null);
  const [working, setWorking] = React.useState(false);
  const [requestingReview, setRequestingReview] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const loadedRun = await fetchLatestReconciliation(investigationId);
      const [loadedResults, loadedPatterns] = await Promise.all([
        fetchReconciliationResults(investigationId, loadedRun.id),
        fetchFinancialInvestigationPatterns(investigationId),
      ]);
      setRun(loadedRun);
      setResults(loadedResults);
      setPatterns(loadedPatterns);
      setSelectedId(current => current ?? loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null);
    } catch (loadError) {
      if (loadError instanceof ApiClientError && loadError.status === 404) {
        setRun(null);
        setResults([]);
        setPatterns([]);
        return;
      }
      setError(errorMessage(loadError));
    }
  }, [investigationId]);

  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => {
    fetchProviderHealth().then(setProviderHealth).catch(() => setProviderHealth(null));
  }, []);

  const selected = results.find(item => item.id === selectedId) ?? null;
  const exceptions = results.filter(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS");

  async function reconcile() {
    setWorking(true); setError(null);
    try {
      const dataset = await normalizeDataset(investigationId);
      const completed = await runInvestigationReconciliation(investigationId, dataset.id);
      const [loadedResults, loadedPatterns] = await Promise.all([
        fetchReconciliationResults(investigationId, completed.id),
        fetchFinancialInvestigationPatterns(investigationId),
      ]);
      setRun(completed); setResults(loadedResults); setPatterns(loadedPatterns);
      setSelectedId(loadedResults.find(item => item.status === "EXCEPTION" || item.status === "AMBIGUOUS")?.id ?? null);
      setInvestigation(null); setLifecycle(null); setReviewRequest(null);
    } catch (runError) { setError(errorMessage(runError)); }
    finally { setWorking(false); }
  }

  async function inspect(result: ApiReconciliationResult) {
    if (!run) return;
    setSelectedId(result.id); setInvestigation(null); setLifecycle(null); setReviewRequest(null); setError(null); setWorking(true);
    try {
      const [loadedInvestigation, loadedLifecycle] = await Promise.allSettled([
        fetchReconciliationInvestigation(investigationId, run.id, result.id),
        fetchLifecycle(result.order_id),
      ]);
      if (loadedInvestigation.status === "fulfilled") setInvestigation(loadedInvestigation.value);
      if (loadedLifecycle.status === "fulfilled") setLifecycle(loadedLifecycle.value);
      const failed = [loadedInvestigation, loadedLifecycle].find(
        item => item.status === "rejected" && !(item.reason instanceof ApiClientError && item.reason.status === 404),
      );
      if (failed?.status === "rejected") setError(errorMessage(failed.reason));
    }
    finally { setWorking(false); }
  }

  async function investigate() {
    if (!run || !selected) return;
    setWorking(true); setError(null);
    try { setInvestigation(await investigateReconciliationResult(investigationId, run.id, selected.id)); }
    catch (investigateError) { setError(errorMessage(investigateError)); }
    finally { setWorking(false); }
  }

  async function requestReview() {
    if (!run || !selected) return;
    setRequestingReview(true); setError(null);
    try { setReviewRequest(await requestFinancialResolution(investigationId, run.id, selected.id, reviewActionFor(selected.exception_type), requestId())); }
    catch (reviewError) { setError(errorMessage(reviewError)); }
    finally { setRequestingReview(false); }
  }

  async function decideReview(decision: "approve" | "reject") {
    if (!reviewRequest) return;
    setWorking(true); setError(null);
    try {
      const result = decision === "approve"
        ? await approveResolution(reviewRequest.request_id, requestId())
        : await rejectResolution(reviewRequest.request_id, requestId());
      setReviewRequest(current => current ? { ...current, status: result.request_status, approvals_received: result.approvals_received } : current);
    } catch (decisionError) { setError(errorMessage(decisionError)); }
    finally { setWorking(false); }
  }

  const actor = currentActor();
  const canApprove = actor.role === "FINANCE_MANAGER" || actor.role === "CONTROLLER";
  return <Card id="reconciliation" className="mt-4"><CardHeader><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle>Reconciliation and investigation</CardTitle><CardDescription>Deterministic rules establish the financial result. AI only investigates selected exceptions using read-only, verifiable evidence.</CardDescription></div>{run && <Button variant="outline" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? "Running…" : "Run again"}</Button>}</div>{providerHealth && <ProviderHealthSummary health={providerHealth} />}</CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-3"><AlertDescription>{error}</AlertDescription></Alert>}{!run ? <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center"><div className="text-sm font-semibold text-foreground">Ready to reconcile</div><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted-foreground">Normalize the confirmed source mappings into an immutable dataset, then run the deterministic lifecycle checks. This creates the exception queue for evidence review.</p><Button className="mt-4" size="sm" onClick={() => void reconcile()} disabled={working}>{working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{working ? "Preparing run…" : "Normalize and reconcile"}</Button></div> : <><ReconciliationStory run={run} results={results} currency={currency} /><div className="mt-4 rounded-md border border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">Input integrity: {run.records_loaded.toLocaleString()} / {run.records_expected.toLocaleString()} normalized records accounted for · consumed {run.records_consumed.toLocaleString()} · rejected {run.rejected_record_count.toLocaleString()} · orphan {run.orphan_record_count.toLocaleString()} · {run.failure_reason ?? "No integrity exceptions."}</div>{patterns.length > 0 && <div className="mt-4 rounded-md border border-border p-3 text-xs"><div className="font-semibold text-foreground">Recurring signals</div><div className="mt-2 grid gap-2 sm:grid-cols-2">{patterns.map(pattern => <div key={pattern.pattern_id} className="rounded-md bg-muted/20 p-2 text-muted-foreground"><span className="font-semibold text-foreground">{statusLabel(pattern.exception_type)}</span> · {pattern.occurrence_count} occurrences · {(Number(pattern.associated_exposure_minor) / 100).toLocaleString("en-IN", { style: "currency", currency })}</div>)}</div></div>}{exceptions.length === 0 ? <Alert variant="info" className="mt-4"><AlertTitle>All lifecycles reconciled</AlertTitle><AlertDescription>No exception or ambiguous association requires investigation in this run.</AlertDescription></Alert> : <div id="exceptions" className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.4fr)]"><div><div className="mb-2 flex items-center justify-between"><div className="text-xs font-semibold text-foreground">Top exception categories</div><span className="text-[11px] text-muted-foreground">{exceptions.length} result(s)</span></div><div className="max-h-96 space-y-2 overflow-auto pr-1">{exceptions.map(item => <Button type="button" variant="ghost" key={item.id} onClick={() => void inspect(item)} className={`w-full rounded-md border p-3 text-left text-xs ${selected?.id === item.id ? "border-primary bg-primary/5" : "border-border bg-muted/20"}`}><div className="flex items-center justify-between gap-2"><span className="font-semibold text-foreground">{item.order_id}</span><StatusBadge status={item.status} /></div><div className="mt-1 text-[11px] text-muted-foreground">{statusLabel(item.exception_type ?? "AMBIGUOUS_ASSOCIATION")} · {statusLabel(item.severity)} · {(item.exposure_minor / 100).toLocaleString("en-IN", { style: "currency", currency })}</div></Button>)}</div></div>{selected && <div className="rounded-md border border-border p-4 text-xs"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="font-semibold text-foreground">Exception investigation</div><div className="mt-1 text-[11px] text-muted-foreground">{selected.order_id} · {statusLabel(selected.exception_type ?? "AMBIGUOUS_ASSOCIATION")} · deterministic findings: {selected.findings.map(item => item.code).join(", ")}</div></div><Button size="sm" onClick={() => void investigate()} disabled={working}>{working ? "Investigating…" : investigation ? "Re-run investigation" : "Investigate with AI"}</Button></div>{lifecycle && <LifecyclePreview lifecycle={lifecycle} exceptionType={selected.exception_type} />}{investigation ? <><InvestigationStory investigation={investigation} /><div className="mt-3 grid gap-3 sm:grid-cols-3"><MetricCell label="Root cause" value={investigation.root_cause_code ?? "Unresolved"} /><MetricCell label="Evidence score" value={`${investigation.evidence_score}/100`} /><MetricCell label="Verifier" value={investigation.verifier_passed ? "Passed" : "Review required"} /></div><EvidencePanel title="Supporting evidence" items={investigation.supporting_evidence} /><EvidencePanel title="Contradictory evidence" items={investigation.contradictory_evidence} />{investigation.rejected_evidence.length > 0 && <EvidencePanel title="Rejected evidence" items={investigation.rejected_evidence} />}</> : <p className="mt-6 text-center text-xs text-muted-foreground">Select “Investigate with AI” to produce a bounded, evidence-backed assessment.</p>}{reviewRequest ? <div className="mt-4 rounded-md border border-info/30 bg-info/5 p-3"><div className="font-semibold text-foreground">Human review · {statusLabel(reviewRequest.status)}</div><div className="mt-1 text-[11px] text-muted-foreground">Requested by {reviewRequest.requester_id} · {reviewRequest.approvals_received}/{reviewRequest.required_approvals} approvals · {statusLabel(reviewRequest.action_code)}</div>{reviewRequest.status === "PENDING_APPROVAL" && (canApprove && actor.id !== reviewRequest.requester_id ? <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={() => void decideReview("approve")} disabled={working}>Approve</Button><Button variant="outline" size="sm" onClick={() => void decideReview("reject")} disabled={working}>Reject</Button></div> : <p className="mt-3 text-[11px] text-muted-foreground">Waiting for a different authorized reviewer. The requester cannot approve their own request.</p>)}</div> : <Button variant="outline" className="mt-4" size="sm" onClick={() => void requestReview()} disabled={working || requestingReview}>{requestingReview ? "Requesting review…" : "Request human review"}</Button>}</div>}</div>}</>}</CardContent></Card>;
}

export function FinancialInvestigationSourcesPage({ investigationId }: { investigationId: string }) {
  const [investigation, setInvestigation] = React.useState<ApiFinancialInvestigation | null>(null);
  const [sources, setSources] = React.useState<ApiSourceFile[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState<string[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [generating, setGenerating] = React.useState(false);
  const [demoForm, setDemoForm] = React.useState({ orders: 25, seed: 42, anomalyRatePercent: 30 });

  const load = React.useCallback(() => Promise.all([fetchFinancialInvestigation(investigationId), fetchSourceFiles(investigationId)]).then(([loadedInvestigation, loadedSources]) => { setInvestigation(loadedInvestigation); setSources(loadedSources); }).catch(loadError => setError(errorMessage(loadError))).finally(() => setLoading(false)), [investigationId]);
  React.useEffect(() => { void load(); }, [load]);

  async function handleFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length === 0) return;
    setError(null); setNotice(null);
    const invalid = files.find(file => !allowedExtensions.some(extension => file.name.toLowerCase().endsWith(extension)));
    if (invalid) { setError(`${invalid.name} is not supported. Upload CSV or XLSX files only.`); return; }
    setUploading(files.map(file => file.name));
    for (const file of files) {
      try { const uploaded = await uploadSourceFile(investigationId, file, requestId()); setSources(current => [...current, uploaded]); }
      catch (uploadError) { setError(`${file.name}: ${errorMessage(uploadError)}`); }
      finally { setUploading(current => current.filter(name => name !== file.name)); }
    }
    setNotice("Sources uploaded. Analyze each source to review its bounded classification and mapping proposals.");
  }

  async function handleDemoGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sources.length > 0) return;
    setGenerating(true); setError(null); setNotice(null);
    const payload: DemoDataRequest = { orders: demoForm.orders, seed: demoForm.seed, anomaly_rate: demoForm.anomalyRatePercent / 100 };
    try {
      const result = await generateDemoData(investigationId, payload, requestId());
      setSources(result.sources);
      setNotice(`Generated ${result.orders.toLocaleString()} synthetic orders and attached ${result.sources.length} source files. Continue with source analysis and mapping review.`);
    } catch (generationError) { setError(errorMessage(generationError)); }
    finally { setGenerating(false); }
  }

  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation…</div>;
  if (!investigation) return <Alert variant="destructive"><AlertTitle>Investigation not found</AlertTitle><AlertDescription>{error ?? "This investigation is not available in the current workspace."}</AlertDescription></Alert>;
  return <>
    <div className="mb-5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Link href="/investigations" className="flex items-center gap-1 font-semibold hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Investigations</Link><span>/</span><span>{investigation.id}</span></div>
    <InvestigationStageNav investigationId={investigation.id} /><PageHeading eyebrow="Source intake" title={investigation.name} description="Upload trusted exports for this investigation. FinTrace validates file structure at the API boundary before any mapping or analysis begins."><Button asChild variant="outline" size="sm"><Link href={`/investigations/${investigation.id}`}>Overview</Link></Button></PageHeading>
    {error && <Alert variant="destructive" className="mb-4"><AlertTitle>Source intake needs attention</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {notice && <Alert variant="info" className="mb-4"><CheckCircle2 className="mr-2 inline h-4 w-4" />{notice}</Alert>}
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]"><div className="grid gap-4"><Card><CardHeader><CardTitle>Upload source files</CardTitle><CardDescription>Supported formats: CSV and XLSX. Maximum file size is 10 MB per file.</CardDescription></CardHeader><CardContent><label htmlFor="source-upload" className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 px-6 py-12 text-center transition-colors hover:border-primary/50 hover:bg-muted/50"><UploadCloud className="h-8 w-8 text-primary" /><span className="mt-3 text-sm font-semibold text-foreground">Choose source exports</span><span className="mt-1 text-xs text-muted-foreground">You can select multiple files. Server validation remains authoritative.</span><span className="mt-4 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground">Browse files</span><FileInput id="source-upload" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple onChange={handleFiles} /></label>{uploading.length > 0 && <div className="mt-4 space-y-2" role="status">{uploading.map(name => <div key={name} className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Uploading {name}…</div>)}</div>}</CardContent></Card><Card><CardHeader><CardTitle>Generate fresh synthetic data</CardTitle><CardDescription>Use the same upload boundary with reproducible, generated CSV sources. No fixture snapshot is substituted.</CardDescription></CardHeader><CardContent><form onSubmit={handleDemoGenerate} className="space-y-4"><div><label htmlFor="demo-orders" className="text-xs font-semibold text-foreground">Orders</label><Input id="demo-orders" type="number" min={1} max={2000} className="mt-2" value={demoForm.orders} onChange={event => setDemoForm({ ...demoForm, orders: Number(event.target.value) || 1 })} /></div><div className="grid gap-3 sm:grid-cols-2"><div><label htmlFor="demo-seed" className="text-xs font-semibold text-foreground">Seed</label><Input id="demo-seed" type="number" min={0} max={2147483647} className="mt-2" value={demoForm.seed} onChange={event => setDemoForm({ ...demoForm, seed: Number(event.target.value) || 0 })} /></div><div><label htmlFor="demo-anomaly-rate" className="text-xs font-semibold text-foreground">Anomaly rate %</label><Input id="demo-anomaly-rate" type="number" min={0} max={100} step={1} className="mt-2" value={demoForm.anomalyRatePercent} onChange={event => setDemoForm({ ...demoForm, anomalyRatePercent: Number(event.target.value) || 0 })} /></div></div>{sources.length > 0 && <p className="text-[11px] leading-5 text-muted-foreground">Fresh generation is available only before sources are attached. Remove the current set if you want to generate a different one.</p>}<Button type="submit" size="sm" disabled={generating || sources.length > 0}><Sparkles className="h-3.5 w-3.5" />{generating ? "Generating…" : "Generate and attach"}</Button></form></CardContent></Card></div><Card><CardHeader><CardTitle>Ingestion safeguards</CardTitle></CardHeader><CardContent className="space-y-4 text-xs"><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Files are scoped to <strong className="text-foreground">{investigation.organization_id}</strong> and linked to this investigation.</p></div><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Only bounded structural metadata is used for the next mapping step. Raw files are not sent to an AI provider.</p></div><div className="flex gap-3"><ShieldCheck className="h-4 w-4 shrink-0 text-success" /><p className="leading-5 text-muted-foreground">Uploaded content is untrusted input and cannot change financial state by itself.</p></div></CardContent></Card></div>
    <Card className="mt-4"><CardHeader><CardTitle>Attached sources <span className="ml-1 text-muted-foreground">({sources.length})</span></CardTitle><CardDescription>Analyze each source, review the proposed mappings, and explicitly confirm required fields before continuing.</CardDescription></CardHeader><CardContent>{sources.length === 0 ? <div className="py-8 text-center text-sm text-muted-foreground">No source files attached yet.</div> : sources.map(source => <SourceFileRow key={source.id} investigationId={investigation.id} source={source} onDeleted={sourceId => setSources(current => current.filter(item => item.id !== sourceId))} onChanged={updated => setSources(current => current.map(item => item.id === updated.id ? updated : item))} />)}</CardContent></Card>
  </>;
}

export function FinancialInvestigationDetailPage({ investigationId }: { investigationId: string }) {
  const [investigation, setInvestigation] = React.useState<ApiFinancialInvestigation | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { fetchFinancialInvestigation(investigationId).then(setInvestigation).catch(loadError => setError(errorMessage(loadError))).finally(() => setLoading(false)); }, [investigationId]);
  if (loading) return <div role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading investigation…</div>;
  if (!investigation) return <Alert variant="destructive"><AlertTitle>Investigation not found</AlertTitle><AlertDescription>{error ?? "This investigation is not available in the current workspace."}</AlertDescription></Alert>;
  return <><div className="mb-5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Link href="/investigations" className="flex items-center gap-1 font-semibold hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Investigations</Link><span>/</span><span>{investigation.id}</span></div><PageHeading eyebrow="Financial investigation" title={investigation.name} description={investigation.description || "No description provided."}><StatusBadge status={investigation.status} /></PageHeading><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Status</div><div className="mt-2"><StatusBadge status={investigation.status} /></div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Source files</div><div className="mt-2 text-xl font-bold text-foreground">{investigation.source_file_count}</div><div className="text-xs text-muted-foreground">Attached to this workspace</div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Period</div><div className="mt-2 text-sm font-semibold text-foreground">{formatDate(investigation.period_start)}</div><div className="text-xs text-muted-foreground">to {formatDate(investigation.period_end)}</div></CardContent></Card><Card><CardContent className="p-5"><div className="text-[10px] uppercase tracking-wide text-muted-foreground">Base currency</div><div className="mt-2 text-xl font-bold text-foreground">{investigation.base_currency}</div><div className="text-xs text-muted-foreground">Financial calculations remain deterministic</div></CardContent></Card></div><RelationshipReview investigationId={investigation.id} /><ReconciliationRunPanel investigationId={investigation.id} currency={investigation.base_currency} /><Card className="mt-4"><CardHeader><CardTitle>Investigation workflow</CardTitle><CardDescription>Source intake is the first controlled stage. Mapping, relationship review, normalization, lifecycle construction, and reconciliation follow after the source contract is confirmed.</CardDescription></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-4">{["Upload sources", "Confirm mappings", "Review relationships", "Reconcile outcomes"].map((step, index) => <div key={step} className="rounded-lg border border-border p-4"><div className="flex items-center gap-2 text-xs font-semibold text-foreground"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">{index + 1}</span>{step}</div><p className="mt-2 text-[11px] leading-5 text-muted-foreground">{index === 0 ? "Attach and validate your CSV/XLSX exports." : index === 1 ? "Review and confirm every required mapping." : index === 2 ? "Accept or reject deterministic relationship evidence." : "Run immutable-dataset reconciliation and inspect exceptions."}</p></div>)}</div><Button asChild className="mt-5" size="sm"><Link href={`/investigations/${investigation.id}/sources`}>Manage source files <ArrowRight className="h-3.5 w-3.5" /></Link></Button></CardContent></Card></>;
}
