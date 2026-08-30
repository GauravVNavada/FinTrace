import * as React from "react";
import { cn } from "../utils";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => (
  <select ref={ref} className={cn("flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50", className)} {...props} />
));
Select.displayName = "Select";
