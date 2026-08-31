import * as React from "react";
import { cn } from "../utils";

export const FileInput = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, type = "file", ...props }, ref) => (
  <input ref={ref} type={type} className={cn("sr-only", className)} {...props} />
));
FileInput.displayName = "FileInput";
