import { Badge } from "@fintrace/ui";
import type { ExceptionStatus, Severity } from "../lib/types";

const severityStyles: Record<Severity, string> = {
  CRITICAL: "bg-rose-100 text-rose-700",
  HIGH: "bg-orange-100 text-orange-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  LOW: "bg-slate-100 text-slate-600"
};

const statusStyles: Record<ExceptionStatus, string> = {
  OPEN: "bg-rose-50 text-rose-700",
  IN_REVIEW: "bg-amber-50 text-amber-700",
  RESOLVED: "bg-emerald-50 text-emerald-700",
  ESCALATED: "bg-violet-50 text-violet-700"
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={severityStyles[severity]}><span className="mr-1 h-1.5 w-1.5 rounded-full bg-current" />{severity}</Badge>;
}

export function StatusBadge({ status }: { status: ExceptionStatus }) {
  return <Badge className={statusStyles[status]}>{status.replace("_", " ")}</Badge>;
}
