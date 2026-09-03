import * as React from "react";
import { cn } from "../utils";

export function EmptyState({
  icon,
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  icon?: React.ReactNode;
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card px-6 py-12 text-center", className)}>
      {icon && <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground">{icon}</div>}
      {eyebrow && <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">{eyebrow}</div>}
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">{description}</p>
      {actions && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{actions}</div>}
    </div>
  );
}
