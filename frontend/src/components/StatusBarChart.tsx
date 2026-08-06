import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART, statusColor } from "@/lib/chart";

interface Datum {
  status: string;
  count: number;
}

const ROW_HEIGHT = 44; // px per category — keeps bars spaced, never compressed
const MIN_HEIGHT = 200;

/**
 * Horizontal status bar chart. Each bar is coloured by its semantic status
 * (see lib/chart.statusColor), value labels sit at the bar end, and the chart
 * grows in height with the number of categories so many stages never get
 * squeezed into a small box.
 */
export function StatusBarChart({ data }: { data: Datum[] }) {
  if (!data || data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">No data yet</div>;
  }

  const height = Math.max(MIN_HEIGHT, data.length * ROW_HEIGHT + 16);
  const max = Math.max(...data.map((d) => d.count));

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          barCategoryGap="28%"
          margin={{ left: 4, right: 36, top: 4, bottom: 4 }}
        >
          <CartesianGrid horizontal={false} stroke={CHART.grid} strokeDasharray="3 3" />
          <XAxis
            type="number"
            allowDecimals={false}
            domain={[0, Math.ceil(max * 1.1) + 1]}
            stroke={CHART.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="status"
            width={152}
            interval={0}
            stroke={CHART.axis}
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(15,23,42,0.04)" }}
            contentStyle={{ borderRadius: 8, border: `1px solid ${CHART.grid}`, fontSize: 12 }}
            formatter={(value) => [value, "Count"]}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.status} fill={statusColor(d.status)} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              offset={8}
              fontSize={12}
              fontWeight={600}
              fill={CHART.label}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
