"use client";

import * as React from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@fintrace/ui";
import { demoLogin } from "../lib/api-client";

const identities = [
  { role: "ANALYST" as const, label: "Analyst", description: "Review deterministic findings and request investigation." },
  { role: "FINANCE_MANAGER" as const, label: "Finance Manager", description: "Review exceptions and approve eligible low-value actions." },
  { role: "CONTROLLER" as const, label: "Controller", description: "Review investigations, approvals, patterns, evaluations, and audit." },
];

export function LoginPage() {
  const router = useRouter();
  const [selected, setSelected] = React.useState<(typeof identities)[number]["role"]>("CONTROLLER");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function continueAs(role = selected) {
    setLoading(true); setError(null);
    try {
      const session = await demoLogin(role);
      window.localStorage.setItem("fintrace.access_token", session.access_token);
      window.localStorage.setItem("fintrace.identity", JSON.stringify(session));
      router.push("/");
    } catch {
      setError("The demo identity could not be created. Check that the API is running.");
      setLoading(false);
    }
  }

  return <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10"><div className="w-full max-w-5xl"><div className="mb-8 max-w-xl"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">F</div><div><div className="text-xl font-bold tracking-tight text-foreground">FinTrace</div><div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Financial operations control</div></div></div><h1 className="mt-10 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">See where the transaction lifecycle broke.</h1><p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">A controlled demo workspace for deterministic reconciliation, evidence-bounded investigation, and human review.</p></div><Card className="max-w-3xl"><CardHeader><div className="flex items-start justify-between gap-4"><div><CardTitle>Choose demo identity</CardTitle><p className="mt-1 text-xs text-muted-foreground">The API issues a signed development identity for this local workspace.</p></div><Badge variant="outline"><ShieldCheck className="mr-1 h-3 w-3" />RBAC enforced</Badge></div></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-3">{identities.map(identity => <Button type="button" variant="ghost" key={identity.role} onClick={() => setSelected(identity.role)} className={`h-auto rounded-lg border p-4 text-left transition-colors ${selected === identity.role ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"}`}><div className="flex w-full items-center justify-between gap-2"><span className="text-sm font-semibold text-foreground">{identity.label}</span>{selected === identity.role && <span className="h-2 w-2 rounded-full bg-primary" />}</div><p className="mt-2 w-full text-xs leading-5 text-muted-foreground">{identity.description}</p></Button>)}</div>{error && <Alert variant="destructive" className="mt-4"><AlertTitle>Login unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<div className="mt-5 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between"><div className="text-xs text-muted-foreground">Recommended for review: <span className="font-semibold text-foreground">Controller</span></div><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void continueAs("CONTROLLER")} disabled={loading}>Judge Demo · Controller</Button><Button onClick={() => void continueAs()} disabled={loading}>{loading ? "Signing in…" : selected === "CONTROLLER" ? "Continue as Controller" : `Continue as ${identities.find(item => item.role === selected)?.label}`}<ArrowRight className="h-3.5 w-3.5" /></Button></div></div></CardContent></Card></div></main>;
}
