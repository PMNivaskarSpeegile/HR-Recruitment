import { useState } from "react";
import { AlertCircle, Clock } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetBody,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { statusVariant } from "@/lib/status";
import { fmtDateTime } from "@/lib/format";
import type { ColumnDef } from "@tanstack/react-table";
import { useMappings, useMappingTimeline } from "./api";
import type { Mapping, TimelineEvent } from "./types";

// Distinct timeline markers by event kind (mirrors the Candidate Drawer).
const MARKER: Record<string, string> = {
  created: "bg-primary",
  status_change: "bg-teal",
  screening_feedback: "bg-warning",
  email: "bg-primary/60",
  duplicate_resolution: "bg-warning",
};

/** The current pipeline status label for a mapping: the closing outcome if the
 *  application is closed, otherwise the live stage. */
function latestStatus(m: Mapping): string {
  return (m.is_closed ? m.latest_outcome_name : m.application_stage_name) ?? "—";
}

/** Read-only Activity Timeline for one candidate on the selected requirement.
 *  Communication/activity history only — no resume, verify, update, or status
 *  actions. */
function CommActivityDrawer({ mapping, onClose }: { mapping: Mapping | null; onClose: () => void }) {
  const { data, isLoading, isError } = useMappingTimeline(mapping?.mapping_id ?? null);
  const events: TimelineEvent[] = data?.timeline ?? [];
  return (
    <Sheet open={!!mapping} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader className="pr-10">
          <SheetTitle>{mapping?.candidate_name ?? "Candidate"}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">{mapping?.cv_serial}</span>
            {mapping && <Badge variant={statusVariant(latestStatus(mapping))}>{latestStatus(mapping)}</Badge>}
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="py-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Activity timeline
          </div>
          {isError ? (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" /> Couldn't load the activity timeline.
            </div>
          ) : isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-11 w-full rounded-lg" />
              <Skeleton className="h-11 w-full rounded-lg" />
              <Skeleton className="h-11 w-full rounded-lg" />
            </div>
          ) : events.length === 0 ? (
            <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
          ) : (
            <ol className="relative space-y-3 border-l border-border pl-4">
              {events.map((e, i) => (
                <li key={i} className="relative">
                  <span
                    className={cn(
                      "absolute -left-[1.3rem] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-card",
                      MARKER[e.type] ?? "bg-muted-foreground/40",
                    )}
                  />
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm font-medium leading-tight">{e.title}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{fmtDateTime(e.timestamp)}</span>
                  </div>
                  {e.detail && <p className="mt-0.5 text-xs text-muted-foreground">{e.detail}</p>}
                  {e.actor && <p className="text-[11px] text-muted-foreground/80">by {e.actor}</p>}
                </li>
              ))}
            </ol>
          )}
        </SheetBody>

        <SheetFooter>
          <SheetClose asChild>
            <Button variant="ghost" size="sm" className="ml-auto">
              Close
            </Button>
          </SheetClose>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

/** Communication tab: every candidate in the requirement's pipeline (all stages
 *  from Shortlisted onward) with their latest status. Selecting one opens a
 *  read-only activity-history drawer for that candidate on this requirement. */
export function CommunicationsPanel({ reqId }: { reqId: string }) {
  const [selected, setSelected] = useState<Mapping | null>(null);
  const mappings = useMappings(reqId, ""); // no stage filter → all pipeline candidates
  const rows = mappings.data?.results ?? [];

  const columns: ColumnDef<Mapping>[] = [
    {
      accessorKey: "cv_serial",
      header: "CV",
      cell: ({ row }) => <span className="font-medium">{row.original.cv_serial}</span>,
    },
    {
      accessorKey: "candidate_name",
      header: "Candidate",
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="font-medium">{row.original.candidate_name}</div>
          <div className="text-xs text-muted-foreground">{row.original.email}</div>
        </div>
      ),
    },
    {
      id: "status",
      header: "Latest status",
      enableSorting: false,
      cell: ({ row }) => <Badge variant={statusVariant(latestStatus(row.original))}>{latestStatus(row.original)}</Badge>,
    },
    {
      id: "updated",
      header: "Last activity",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="inline-flex items-center gap-1 text-muted-foreground">
          <Clock className="h-3 w-3" /> {fmtDateTime(row.original.updated_on ?? row.original.created_on)}
        </span>
      ),
    },
  ];

  return (
    <div>
      <DataTable
        columns={columns}
        data={rows}
        isLoading={mappings.isLoading}
        searchPlaceholder="Search candidates…"
        emptyMessage="No candidates in this requirement's pipeline yet."
        onRowClick={(m) => setSelected(m)}
      />
      <CommActivityDrawer mapping={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
