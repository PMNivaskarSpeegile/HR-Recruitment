import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Card wrapper for a dashboard chart. The body has consistent padding but no
 * forced height — each chart sizes itself (the donut is fixed, the bar chart
 * grows with its categories) so nothing is squeezed or left with dead space.
 */
export function ChartCard({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col shadow-card", className)}>
      <CardHeader className="space-y-0.5 pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </CardHeader>
      <CardContent className="flex-1 pb-5">{children}</CardContent>
    </Card>
  );
}
