import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART } from "@/lib/chart";

interface Datum {
  recruiter: string;
  requirements: number;
  candidates: number;
}

/**
 * Recruiter workload — grouped vertical bars comparing, per recruiter, the
 * number of assigned requirements vs. candidates currently in their pipeline.
 * Two design-system series colours (blue = requirements, teal = candidates).
 */
export function RecruiterWorkloadChart({ data }: { data: Datum[] }) {
  if (!data || data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">No data yet</div>;
  }

  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 16, right: 8, left: 0, bottom: 4 }} barGap={4} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke={CHART.grid} strokeDasharray="3 3" />
          <XAxis
            dataKey="recruiter"
            interval={0}
            stroke={CHART.axis}
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tickMargin={8}
          />
          <YAxis
            allowDecimals={false}
            stroke={CHART.axis}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={28}
          />
          <Tooltip
            cursor={{ fill: "rgba(15,23,42,0.04)" }}
            contentStyle={{ borderRadius: 8, border: `1px solid ${CHART.grid}`, fontSize: 12 }}
          />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <Bar dataKey="requirements" name="Requirements" fill={CHART.primary} radius={[6, 6, 0, 0]} maxBarSize={44}>
            <LabelList dataKey="requirements" position="top" fontSize={11} fontWeight={600} fill={CHART.label} />
          </Bar>
          <Bar dataKey="candidates" name="Candidates in pipeline" fill={CHART.teal} radius={[6, 6, 0, 0]} maxBarSize={44}>
            <LabelList dataKey="candidates" position="top" fontSize={11} fontWeight={600} fill={CHART.label} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
