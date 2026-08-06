import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Briefcase,
  Users,
  Target,
  Building2,
  UserCog,
  Sparkles,
  GitBranch,
  CheckCircle2,
  CalendarClock,
  BarChart3,
  UserCheck,
  UserPlus,
  FilePlus2,
  DoorOpen,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/StatCard";
import { ChartCard } from "@/components/ChartCard";
import { StatusBarChart } from "@/components/StatusBarChart";
import { DonutChart } from "@/components/DonutChart";
import { RecruiterWorkloadChart } from "@/components/RecruiterWorkloadChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { statusVariant } from "@/lib/status";
import { cn } from "@/lib/utils";
import { useDashboard } from "./api";
import type { ActivityItem, DashboardData } from "./types";

// Admin KPI cards drill down into the relevant module with a filter applied.
const KPI_LINK: Record<string, string> = {
  active_requirements: "/requirements?status=active",
  open_positions: "/requirements?status=active",
  in_pipeline: "/pipeline",
  // NOTE: "joined_this_month" intentionally has NO drill-down — it counts
  // this-month candidate joins, which no existing list reproduces (a
  // requirement-status list would show an unrelated all-time set). Better a
  // non-clickable tile than a link whose count never matches the destination.
  active_recruiters: "/admin?resource=users",
  active_clients: "/admin?resource=clients",
};

// Admin task rows drill down to the filtered list that resolves the task.
const ADMIN_TASK_LINK: Record<string, string> = {
  requirements_without_recruiter: "/requirements?missing=recruiter",
  requirements_without_hiring_manager: "/requirements?missing=hm",
  possible_duplicate_review: "/duplicate-reviews",
  requirements_on_hold_30d: "/requirements?status=HOLD",
  inactive_users: "/admin?resource=users",
};

/** Colour-coded idle heat for the Needs-attention list. */
function idleTone(days: number): { text: string; dot: string } {
  if (days > 30) return { text: "text-destructive", dot: "bg-destructive" };
  if (days >= 15) return { text: "text-orange-500", dot: "bg-orange-500" };
  if (days >= 7) return { text: "text-warning", dot: "bg-warning" };
  return { text: "text-success", dot: "bg-success" };
}

// A requirement filtered into the list = "open this requirement" until a
// dedicated detail view exists.
const reqLink = (tracker: string) => `/requirements?q=${encodeURIComponent(tracker)}`;

const KPI_ICON: Record<string, LucideIcon> = {
  requirements: Briefcase,
  active_requirements: Briefcase,
  my_requirements: Briefcase,
  assigned_requirements: Briefcase,
  candidates: Users,
  candidates_uploaded: Users,
  open_positions: Target,
  clients: Building2,
  active_clients: Building2,
  users: UserCog,
  skills: Sparkles,
  in_pipeline: GitBranch,
  positions_filled: CheckCircle2,
  total_positions: Target,
  total_filled_positions: CheckCircle2,
  candidates_available: Users,
  joined_this_month: UserCheck,
  active_recruiters: UserCog,
  upcoming_screenings: CalendarClock,
};

const SUBTITLE: Record<DashboardData["role"], string> = {
  ADM: "Hiring overview across recruiters, requirements and clients",
  HM: "Your requirements and pipeline",
  REC: "Your workspace",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, isError } = useDashboard();
  const isAdmin = data?.role === "ADM";

  return (
    <div>
      <PageHeader
        title={`Welcome, ${user?.full_name?.split(" ")[0] ?? ""}`}
        description={data ? SUBTITLE[data.role] : "Loading your workspace"}
      />

      {isError && (
        <p className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Could not load the dashboard. Is the backend running?
        </p>
      )}

      {/* KPI row */}
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(190px,1fr))]">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[88px]" />)
          : data?.kpis.map((kpi) => (
              <StatCard
                key={kpi.key}
                label={kpi.label}
                value={kpi.value}
                hint={kpi.hint}
                icon={KPI_ICON[kpi.key] ?? BarChart3}
                to={KPI_LINK[kpi.key]}
              />
            ))}
      </div>

      {data && (isAdmin ? <AdminDashboard data={data} /> : <OperationalDashboard data={data} />)}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Admin — high-level business overview (no operational detail)              */
/* -------------------------------------------------------------------------- */
function AdminDashboard({ data }: { data: DashboardData }) {
  return (
    <>
      {/* Monitoring charts */}
      {(data.requirement_status || data.recruiter_workload) && (
        <div className="mt-4 grid grid-cols-1 items-start gap-4 lg:grid-cols-12">
          {data.requirement_status && (
            <ChartCard title="Requirements by status" subtitle="Across the requirement lifecycle" className="lg:col-span-5">
              <DonutChart data={data.requirement_status} />
            </ChartCard>
          )}
          {data.recruiter_workload && (
            <ChartCard title="Recruiter workload" subtitle="Active requirements vs. candidates in pipeline" className="lg:col-span-7">
              <RecruiterWorkloadChart data={data.recruiter_workload} />
            </ChartCard>
          )}
        </div>
      )}

      {data.pipeline_stages && (
        <div className="mt-4">
          <ChartCard title="Pipeline by stage" subtitle="Candidates across the recruitment flow (org-wide)">
            <StatusBarChart data={data.pipeline_stages} />
          </ChartCard>
        </div>
      )}

      {/* Needs attention + admin oversight tasks */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        {data.stalled_requirements && (
          <ListCard
            title="Needs attention"
            subtitle="Active requirements idle for 14+ days"
            className="lg:col-span-8"
            empty="Nothing stalled — every open requirement is moving"
          >
            {data.stalled_requirements.map((r) => {
              const tone = idleTone(r.idle_days);
              return (
                <li key={r.req_tracker_no}>
                  <Link to={reqLink(r.req_tracker_no)} className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-accent/50">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{r.jd_role_name}</div>
                      <div className="truncate text-xs text-muted-foreground">
                        {r.req_tracker_no} · {r.client_name ?? "—"} · {r.recruiter_name ?? "Unassigned"}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="warning">{r.open_positions} open</Badge>
                      <span className={cn("inline-flex items-center gap-1.5 text-xs", tone.text)}>
                        <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
                        {r.idle_days}d idle
                      </span>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ListCard>
        )}

        {data.admin_tasks && (
          <ListCard title="Pending admin tasks" subtitle="Oversight & data hygiene" className="lg:col-span-4" empty="Nothing pending">
            {data.admin_tasks.map((t) => {
              const to = ADMIN_TASK_LINK[t.key];
              const body = (
                <>
                  <span className="min-w-0 text-sm">{t.label}</span>
                  <Badge variant={t.count > 0 ? "warning" : "success"}>{t.count}</Badge>
                </>
              );
              return (
                <li key={t.key}>
                  {to && t.count > 0 ? (
                    <Link to={to} className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-accent/50">
                      {body}
                    </Link>
                  ) : (
                    <div className="flex items-center justify-between gap-3 px-6 py-3">{body}</div>
                  )}
                </li>
              );
            })}
          </ListCard>
        )}
      </div>

      {/* Client monitoring + recent requirements */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        {data.top_clients && (
          <ListCard title="Top clients" subtitle="By current hiring activity" className="lg:col-span-4" empty="No active client hiring">
            {data.top_clients.map((c) => (
              <li key={c.client_name}>
                <Link
                  to={`/requirements?status=active&q=${encodeURIComponent(c.client_name)}`}
                  className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-accent/50"
                >
                  <span className="min-w-0 truncate text-sm font-medium">{c.client_name}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <span>{c.requirements} active</span>
                    <Badge variant="teal">{c.open_positions} open</Badge>
                  </span>
                </Link>
              </li>
            ))}
          </ListCard>
        )}

        {data.recent_requirements && (
          <ListCard title="Recent requirements" className="lg:col-span-8" empty="No requirements yet">
            {data.recent_requirements.map((r) => (
              <li key={r.req_tracker_no}>
                <Link to={reqLink(r.req_tracker_no)} className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-accent/50">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{r.jd_role_name}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {r.req_tracker_no} · {r.client_name ?? "—"} · {r.recruiter_name ?? "Unassigned"}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {r.positions_filled ?? 0}/{r.positions_required ?? 0} filled
                    </span>
                    {r.status && <Badge variant={statusVariant(r.status)}>{r.status}</Badge>}
                  </div>
                </Link>
              </li>
            ))}
          </ListCard>
        )}
      </div>

      {/* Activity feed — full width, reads as a timeline */}
      {data.recent_activity && (
        <div className="mt-4">
          <ListCard title="Recent activity" empty="No recent activity">
            {data.recent_activity.map((a, i) => (
              <ActivityRow key={`${a.ref ?? a.type}-${i}`} item={a} />
            ))}
          </ListCard>
        </div>
      )}
    </>
  );
}

const ACTIVITY_ICON: Record<ActivityItem["type"], { icon: LucideIcon; className: string }> = {
  requirement_created: { icon: FilePlus2, className: "text-primary" },
  requirement_assigned: { icon: UserCheck, className: "text-primary" },
  candidate_joined: { icon: DoorOpen, className: "text-success" },
  requirement_closed: { icon: XCircle, className: "text-muted-foreground" },
  candidate_added: { icon: UserPlus, className: "text-teal" },
};

function ActivityRow({ item }: { item: ActivityItem }) {
  const { icon: Icon, className } = ACTIVITY_ICON[item.type] ?? ACTIVITY_ICON.requirement_created;
  const inner = (
    <>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${className}`} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm">{item.title}</div>
        <div className="text-xs text-muted-foreground">{fmtDateTime(item.when)}</div>
      </div>
    </>
  );
  return (
    <li>
      {item.ref ? (
        <Link to={reqLink(item.ref)} className="flex items-start gap-3 px-6 py-3 hover:bg-accent/50">
          {inner}
        </Link>
      ) : (
        <div className="flex items-start gap-3 px-6 py-3">{inner}</div>
      )}
    </li>
  );
}

/* -------------------------------------------------------------------------- */
/*  Hiring Manager / Recruiter — their own operational overview               */
/* -------------------------------------------------------------------------- */
function OperationalDashboard({ data }: { data: DashboardData }) {
  return (
    <>
      {data.requirement_status && (
        <div className="mt-4">
          <ChartCard title="Requirements by status" subtitle="Distribution across the requirement lifecycle">
            <DonutChart data={data.requirement_status} />
          </ChartCard>
        </div>
      )}

      {(data.pipeline_stages ?? data.pipeline_status) && (
        <div className="mt-4">
          <ChartCard title="Pipeline by stage" subtitle="Candidates across the recruitment flow">
            <StatusBarChart data={data.pipeline_stages ?? data.pipeline_status ?? []} />
          </ChartCard>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        {data.recent_requirements && (
          <ListCard title="Recent requirements" className="lg:col-span-6" empty="No requirements yet">
            {data.recent_requirements.map((r) => (
              <Row key={r.req_tracker_no} primary={r.jd_role_name} secondary={`${r.req_tracker_no} · ${r.client_name ?? "—"}`} meta={fmtDate(r.req_date)} status={r.status} />
            ))}
          </ListCard>
        )}

        {data.recent_candidates && (
          <ListCard title="Recent candidates" className="lg:col-span-6" empty="No candidates yet">
            {data.recent_candidates.map((c) => (
              <Row key={c.cv_serial} primary={c.candidate_name} secondary={c.cv_serial} meta={fmtDate(c.created_on)} status={c.status} />
            ))}
          </ListCard>
        )}

        {data.upcoming_screenings && (
          <ListCard title="Upcoming screenings" className="lg:col-span-12" empty="No screenings scheduled">
            {data.upcoming_screenings.map((s, i) => (
              <Row key={`${s.req_tracker_no}-${i}`} primary={s.candidate_name} secondary={s.req_tracker_no} meta={fmtDateTime(s.screening_datetime)} status={s.status} />
            ))}
          </ListCard>
        )}
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/*  Shared presentational bits                                                */
/* -------------------------------------------------------------------------- */
function ListCard({
  title,
  subtitle,
  children,
  className,
  empty,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  empty: string;
}) {
  const hasRows = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <Card className={`shadow-card ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </CardHeader>
      <CardContent className="p-0">
        {hasRows ? (
          <ul className="divide-y">{children}</ul>
        ) : (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">{empty}</p>
        )}
      </CardContent>
    </Card>
  );
}

function Row({
  primary,
  secondary,
  meta,
  status,
}: {
  primary: string;
  secondary: string;
  meta: string;
  status?: string | null;
}) {
  return (
    <li className="flex items-center justify-between gap-3 px-6 py-3 transition-colors hover:bg-accent/50">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{primary}</div>
        <div className="truncate text-xs text-muted-foreground">{secondary}</div>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {status && <Badge variant={statusVariant(status)}>{status}</Badge>}
        <span className="text-xs text-muted-foreground">{meta}</span>
      </div>
    </li>
  );
}
