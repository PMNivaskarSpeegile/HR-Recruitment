import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { statusVariant } from "@/lib/status";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { useRequirement, useRequirementStatusHistory } from "./api";
import { PositionsPanel } from "./PositionsPanel";

function StatusHistoryPanel({ reqId }: { reqId: number }) {
  const { data, isLoading } = useRequirementStatusHistory(reqId);
  const rows = data ?? [];
  return (
    <Card className="shadow-card">
      <CardContent className="p-5">
        <h2 className="mb-3 text-lg font-semibold">Status history</h2>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading history…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No status changes recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">When</th>
                  <th className="py-2 pr-3 font-medium">Entity</th>
                  <th className="py-2 pr-3 font-medium">Change</th>
                  <th className="py-2 pr-3 font-medium">By</th>
                  <th className="py-2 pr-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((h) => (
                  <tr key={h.history_id}>
                    <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap">{fmtDateTime(h.changed_on)}</td>
                    <td className="py-2 pr-3">
                      {h.entity_type === "REQUIREMENT" ? "Requirement" : "Position"}
                    </td>
                    <td className="py-2 pr-3">
                      <span className="text-muted-foreground">{h.previous_status ?? "—"}</span> → {h.new_status}
                      <Badge variant={h.change_type === "AUTO" ? "muted" : "secondary"} className="ml-2">
                        {h.change_type === "AUTO" ? "Automatic" : "Manual"}
                      </Badge>
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">{h.changed_by_name ?? "System"}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{h.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  );
}

export default function RequirementDetailsPage() {
  const { id } = useParams();
  const { data: r, isLoading, isError } = useRequirement(id ?? null);

  return (
    <div>
      <Link
        to="/requirements"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Requirements
      </Link>

      {isError ? (
        <p className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Couldn't load this requirement. It may not exist or you may not have access to it.
        </p>
      ) : isLoading || !r ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      ) : (
        <>
          <div className="mb-4">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold">{r.jd_role_name}</h1>
              <Badge variant={statusVariant(r.req_status_name)}>{r.req_status_name}</Badge>
              {r.recruitment_ended ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-destructive px-2 py-0.5 text-xs font-semibold text-white">
                  Recruitment Ended
                </span>
              ) : (
                r.is_expired && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-destructive px-2 py-0.5 text-xs font-semibold text-white">
                    Expired
                  </span>
                )
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {r.req_tracker_no} · {r.client_name} · {r.positions_filled}/{r.positions_open} filled
            </p>
            {r.recruitment_ended ? (
              <p className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                Recruitment has permanently ended for this requirement
                {r.recruitment_ended_on ? ` on ${fmtDate(r.recruitment_ended_on)}` : ""}
                {r.recruitment_ended_by_name ? ` by ${r.recruitment_ended_by_name}` : ""}. The remaining positions were
                withdrawn and the active applications closed; the filled positions and full history are preserved.
              </p>
            ) : (
              r.is_expired && (
                <p className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  Requirement expired on {fmtDate(r.expired_on)}. It is read-only — extend the Target Fill Date to resume
                  normal operations.
                </p>
              )
            )}
          </div>

          <Tabs defaultValue="positions">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="positions">Positions</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <Card className="shadow-card">
                <CardContent className="p-5">
                  <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <Field label="Client" value={r.client_name} />
                    <Field label="Type" value={r.req_type_name} />
                    <Field label="Priority" value={r.priority_name} />
                    <Field label="Recruiter" value={r.recruiter_name ?? "Unassigned"} />
                    <Field label="Hiring manager" value={r.hiring_mgr_name} />
                    <Field label="Location" value={r.location_name} />
                    <Field
                      label="Experience"
                      value={r.exp_min || r.exp_max ? `${r.exp_min ?? "—"}–${r.exp_max ?? "—"} yrs` : null}
                    />
                    <Field label="Rate (LPA)" value={r.jd_rate_lpa} />
                    <Field label="Created" value={r.created_on ? fmtDate(r.created_on) : null} />
                    <Field label="Target close" value={r.target_fill_date ? fmtDate(r.target_fill_date) : null} />
                    <Field label="Client Req ID" value={r.client_req_id} />
                    <div className="col-span-2 sm:col-span-3">
                      <Field label="Skills" value={r.skill_names.length ? r.skill_names.join(", ") : null} />
                    </div>
                    {r.jd_text && (
                      <div className="col-span-2 sm:col-span-3">
                        <dt className="text-xs text-muted-foreground">Job description</dt>
                        <dd className="mt-0.5 whitespace-pre-wrap text-sm">{r.jd_text}</dd>
                      </div>
                    )}
                  </dl>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="positions">
              <PositionsPanel req={r} />
            </TabsContent>

            <TabsContent value="history">
              <StatusHistoryPanel reqId={r.req_id} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
