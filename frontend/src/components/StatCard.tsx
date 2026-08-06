import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  to,
}: {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  hint?: string;
  /** When set, the whole card becomes a drill-down link to this route. */
  to?: string;
}) {
  const card = (
    <Card className={cn("h-full shadow-card", to && "transition-shadow hover:shadow-elevated")}>
      <CardContent className="flex items-center gap-4 p-5">
        {Icon && (
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0">
          <div className="truncate text-sm text-muted-foreground">{label}</div>
          <div className="text-2xl font-bold tracking-tight">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  );

  if (!to) return card;
  return (
    <Link
      to={to}
      className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      {card}
    </Link>
  );
}
