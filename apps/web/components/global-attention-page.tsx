"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@fintrace/ui";
import { fetchFinancialInvestigations } from "../lib/api-client";

export function GlobalAttentionPage() {
  const router = useRouter(); const [message, setMessage] = React.useState<string | null>(null);
  React.useEffect(() => { fetchFinancialInvestigations().then(items => { const latest = items[0]; if (latest) router.replace(`/investigations/${latest.id}/attention`); else setMessage("Start a close to review attention items."); }).catch(() => setMessage("Attention is unavailable until the current close can be loaded.")); }, [router]);
  return message ? <Alert><AlertDescription>{message}</AlertDescription></Alert> : <div role="status" className="text-sm text-muted-foreground">Opening attention…</div>;
}
