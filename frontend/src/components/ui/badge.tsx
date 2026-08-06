import type { HTMLAttributes } from "react";
import { cva } from "class-variance-authority";
import type { VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/10 text-primary",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        success: "border-transparent bg-success/10 text-success",
        warning: "border-transparent bg-warning/15 text-foreground",
        danger: "border-transparent bg-destructive/10 text-destructive",
        teal: "border-transparent bg-teal/10 text-teal",
        muted: "border-transparent bg-muted text-muted-foreground",
        outline: "text-foreground",
        // Distinct palette colours (light bg / dark text) used by status maps.
        blue: "border-transparent bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",
        purple: "border-transparent bg-purple-100 text-purple-800 dark:bg-purple-500/15 dark:text-purple-300",
        orange: "border-transparent bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
        neutral: "border-transparent bg-gray-200 text-gray-800 dark:bg-gray-500/25 dark:text-gray-100",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
