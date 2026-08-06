import { useRef } from "react";
import { createPortal } from "react-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Sector, Tooltip } from "recharts";
import type { PieSectorDataItem } from "recharts";
import { statusColor } from "@/lib/chart";

interface Datum {
  status: string;
  count: number;
}

// Approx tooltip box size, for keeping it on-screen near the viewport edges.
const TT_W = 184;
const TT_H = 84;

/** Enlarged sector for the hovered slice (Material-style "active" emphasis). */
function ActiveSlice(props: PieSectorDataItem) {
  const { cx, cy, innerRadius, outerRadius = 0, startAngle, endAngle, fill } = props;
  return (
    <Sector
      cx={cx}
      cy={cy}
      innerRadius={innerRadius}
      outerRadius={outerRadius + 6}
      startAngle={startAngle}
      endAngle={endAngle}
      fill={fill}
      stroke="hsl(var(--card))"
      strokeWidth={2}
      style={{ transition: "opacity 150ms ease-out" }}
    />
  );
}

/**
 * Tooltip rendered through a portal to <body> with position:fixed, so it can
 * never be clipped by an ancestor's `overflow` (the dashboard's scrolling
 * <main> and the AppShell root both clip) and always paints above the sidebar.
 * Recharts still owns the active state + cursor `coordinate`; we just convert
 * that to viewport coordinates and draw our own box.
 */
function PortalTooltip({
  active,
  payload,
  coordinate,
  total,
  anchor,
}: {
  active?: boolean;
  payload?: readonly any[];
  coordinate?: { x?: number; y?: number };
  total: number;
  anchor: React.RefObject<HTMLDivElement | null>;
}) {
  if (!active || !payload?.length || !coordinate || !anchor.current || typeof window === "undefined") return null;

  const rect = anchor.current.getBoundingClientRect();
  const name = String(payload[0].name);
  const count = Number(payload[0].value);
  const percentage = total ? Math.round((count / total) * 100) : 0;

  // Cursor position in the viewport, nudged off the cursor; flip near edges.
  let left = rect.left + (coordinate.x ?? 0) + 14;
  let top = rect.top + (coordinate.y ?? 0) + 14;
  if (left + TT_W > window.innerWidth) left = rect.left + (coordinate.x ?? 0) - TT_W - 14;
  if (top + TT_H > window.innerHeight) top = rect.top + (coordinate.y ?? 0) - TT_H - 14;
  left = Math.max(8, left);
  top = Math.max(8, top);

  return createPortal(
    <div
      style={{ position: "fixed", left, top, zIndex: 1000, pointerEvents: "none" }}
      className="rounded-[10px] border border-border bg-popover px-3.5 py-2.5 shadow-lg"
    >
      <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-foreground">
        <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: statusColor(name) }} aria-hidden />
        {name}
      </div>
      <div className="text-xs text-muted-foreground">
        Count: <span className="font-medium tabular-nums text-foreground">{count}</span>
      </div>
      <div className="text-xs text-muted-foreground">
        Percentage: <span className="font-medium tabular-nums text-foreground">{percentage}%</span>
      </div>
    </div>,
    document.body
  );
}

/**
 * Donut chart for categorical distributions (e.g. requirements by status).
 * Slices use semantic status colours; the centre shows the total; the legend
 * lists every status with its count; percentages live in the hover tooltip.
 */
export function DonutChart({ data }: { data: Datum[] }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);

  if (!data || data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">No data yet</div>;
  }

  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="flex min-w-0 flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-8">
      {/* overflow-visible is harmless here; the real anti-clip fix is the portal */}
      <div ref={wrapRef} className="relative h-[184px] w-[184px] shrink-0 overflow-visible">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="status"
              innerRadius={54}
              outerRadius={78}
              paddingAngle={2}
              stroke="none"
              isAnimationActive={false}
              activeShape={ActiveSlice}
            >
              {data.map((d) => (
                <Cell key={d.status} fill={statusColor(d.status)} />
              ))}
            </Pie>
            <Tooltip
              allowEscapeViewBox={{ x: true, y: true }}
              isAnimationActive={false}
              wrapperStyle={{ pointerEvents: "none", outline: "none" }}
              content={(props: any) => (
                <PortalTooltip
                  active={props.active}
                  payload={props.payload}
                  coordinate={props.coordinate}
                  total={total}
                  anchor={wrapRef}
                />
              )}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tracking-tight tabular-nums">{total}</span>
          <span className="text-xs text-muted-foreground">Total</span>
        </div>
      </div>

      {/* Legend: status name + count only (percentages are in the tooltip). */}
      <ul className="flex min-w-0 flex-1 flex-wrap gap-x-6 gap-y-2.5">
        {data.map((d) => (
          <li key={d.status} className="flex min-w-0 grow basis-[160px] items-center gap-2 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: statusColor(d.status) }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-muted-foreground" title={d.status}>
              {d.status}
            </span>
            <span className="shrink-0 font-semibold tabular-nums">{d.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
