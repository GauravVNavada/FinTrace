"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@fintrace/ui";
import { fetchFinancialInvestigations } from "../lib/api-client";

export function GlobalAttentionPage() {
  const router = useRouter(); const [message, setMessage] = React.useState<string | null>(null);
  React.useEffect(() => { fetchFinancialInvestigations().then(items => { const canonical = items.find(item => item.name.toLowerCase().startsWith("august 2026 independent close") && item.status === "RECONCILED" && item.source_file_count >= 7) ?? items.find(item => item.name.toLowerCase().startsWith("august 2026 independent close")); if (canonical) router.replace(`/investigations/${canonical.id}/attention`); else setMessage("Prepare the canonical August close before reviewing attention items."); }).catch(() => setMessage("Attention is unavailable until the current close can be loaded.")); }, [router]);
  return message ? <Alert><AlertDescription>{message}</AlertDescription></Alert> : <div role="status" className="text-sm text-muted-foreground">Opening attention…</div>;
}
