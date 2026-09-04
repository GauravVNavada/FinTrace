"use client";

import * as React from "react";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle, Button, Card, CardContent, CardHeader, CardTitle } from "@fintrace/ui";
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

  return <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10"><div className="w-full max-w-4xl"><div className="mb-8 max-w-xl"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">F</div><div><div className="text-xl font-bold tracking-tight text-foreground">FinTrace</div><div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Financial operations control</div></div></div><h1 className="mt-10 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Close the period with confidence.</h1><p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">Reconcile the financial lifecycle, understand what needs attention, and keep every decision auditable.</p></div><Card className="max-w-2xl"><CardHeader><CardTitle>Financial close workspace</CardTitle><p className="mt-1 text-xs text-muted-foreground">Continue into the local Controller workspace to review the month-end close.</p></CardHeader><CardContent>{error && <Alert variant="destructive" className="mb-4"><AlertTitle>Login unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<Button className="w-full justify-center" onClick={() => void continueAs("CONTROLLER")} disabled={loading}>{loading ? "Opening workspace…" : "Continue to FinTrace"}<ArrowRight className="h-3.5 w-3.5" /></Button><details className="mt-5 rounded-lg border border-border px-4 py-3"><summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-foreground"><span>Other demo roles</span><ChevronDown className="h-4 w-4 text-muted-foreground" /></summary><div className="mt-3 grid gap-2 border-t border-border pt-3 sm:grid-cols-2">{identities.filter(identity => identity.role !== "CONTROLLER").map(identity => <Button type="button" variant="outline" key={identity.role} onClick={() => { setSelected(identity.role); void continueAs(identity.role); }} disabled={loading} className="h-auto justify-start whitespace-normal p-3 text-left"><span><span className="block text-xs font-semibold">{identity.label}</span><span className="mt-1 block text-[11px] font-normal text-muted-foreground">{identity.description}</span></span></Button>)}</div></details></CardContent></Card></div></main>;
}
