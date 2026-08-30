import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./utils";

const badgeVariants = cva("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold leading-5", {
  variants: {
    variant: {
      default: "bg-primary text-primary-foreground",
      secondary: "bg-secondary text-secondary-foreground",
      outline: "border border-border bg-background text-foreground",
      muted: "bg-muted text-muted-foreground",
      success: "bg-success/10 text-success",
      warning: "bg-warning/15 text-warning-foreground",
      destructive: "bg-destructive/10 text-destructive",
      info: "bg-info/10 text-info"
    }
  },
  defaultVariants: { variant: "default" }
});

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
