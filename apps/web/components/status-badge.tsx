import { Badge } from "@fintrace/ui";
import type { ExceptionStatus, Severity } from "../lib/types";

const severityVariants: Record<Severity, "destructive" | "warning" | "muted"> = {
  CRITICAL: "destructive",
  HIGH: "destructive",
  MEDIUM: "warning",
  LOW: "muted"
};

const statusVariants: Record<ExceptionStatus, "destructive" | "warning" | "success" | "info"> = {
  OPEN: "destructive",
  IN_REVIEW: "warning",
  RESOLVED: "success",
  ESCALATED: "info"
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge variant={severityVariants[severity]}><span className="mr-1 h-1.5 w-1.5 rounded-full bg-current" />{severity}</Badge>;
}

export function StatusBadge({ status }: { status: ExceptionStatus }) {
  return <Badge variant={statusVariants[status]}>{status.replace("_", " ")}</Badge>;
}
