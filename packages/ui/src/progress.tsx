import * as React from "react";
import { cn } from "./utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  indicatorClassName?: string;
}

export function Progress({ value, className, indicatorClassName, ...props }: ProgressProps) {
  const boundedValue = Math.max(0, Math.min(100, value));
  return (
    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={boundedValue} className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)} {...props}>
      <div className={cn("h-full rounded-full bg-primary transition-all", indicatorClassName)} style={{ width: `${boundedValue}%` }} />
    </div>
  );
}
