import { useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { AlertCircle, Briefcase, ChevronRight, Clock, ShieldCheck, Tag } from "lucide-react";
import { toast } from "sonner";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiError";
import { cn } from "@/lib/utils";
import { candidateStatusLabel, candidateStatusVariant, statusVariant } from "@/lib/status";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { useCandidateDetail, useClearCandidateStatus, useUntagRequirement } from "./api";
import { TagToRequirementDialog } from "./TagToRequirementDialog";
import type { Candidate, RequirementHistoryItem, TimelineEvent } from "./types";

/** Collapsible panel. Keeps its own open/closed state for as long as the
 *  drawer stays mounted (i.e. remembers it while open). */
function CollapsibleSection({
  icon: Icon,
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-lg border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-accent/40"
      >
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="text-sm font-semibold">{title}</span>
        {meta != null && <span className="ml-auto">{meta}</span>}
      </button>
      {open && <div className="border-t px-3 py-3">{children}</div>}
    </section>
  );
}

function CountChip({ n }: { n: number }) {
  return <span className="rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">{n}</span>;
}

// Distinct timeline markers by event kind.
const MARKER: Record<string, string> = {
  created: "bg-primary",
  status_change: "bg-teal",
  screening_feedback: "bg-warning",
  email: "bg-primary/60",
  duplicate_resolution: "bg-warning",
};

/** Renders a chronological list of timeline events. In the global feed
 *  (`showReq`) each application event is tagged with its requirement; inside a
 *  requirement card the context is implicit so the tag is omitted. */
function TimelineList({ events, showReq = false }: { events: TimelineEvent[]; showReq?: boolean }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">No activity recorded yet.</p>;
  }
  return (
    <ol className="relative space-y-3 border-l border-border pl-4">
      {events.map((e, i) => (
        <li key={i} className="relative">
          <span
            className={cn(
              "absolute -left-[1.3rem] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-card",
              MARKER[e.type] ?? "bg-muted-foreground/40"
            )}
          />
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium leading-tight">{e.title}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{fmtDateTime(e.timestamp)}</span>
          </div>
          {showReq && e.req_id != null && (
            <p className="mt-0.5 flex items-center gap-1 text-[11px]">
              <Briefcase className="h-3 w-3 shrink-0 text-muted-foreground" />
              <span className="font-medium text-foreground/80">{e.req_role ?? "Requirement"}</span>
              <span className="text-muted-foreground">· {e.req_tracker_no}</span>
            </p>
          )}
          {e.detail && <p className="mt-0.5 text-xs text-muted-foreground">{e.detail}</p>}
          {e.actor && <p className="text-[11px] text-muted-foreground/80">by {e.actor}</p>}
        </li>
      ))}
    </ol>
  );
}

/** One requirement's application card. Expands to that application's own
 *  timeline (the global feed filtered to this requirement). */
function RequirementCard({ r, events }: { r: RequirementHistoryItem; events: TimelineEvent[] }) {
  const [open, setOpen] = useState(false);
  const appEvents = events.filter((e) => e.req_id === r.req_id);
  return (
    <li className="rounded-md border">
      <div className="px-3 py-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{r.jd_role_name}</div>
            <div className="text-xs text-muted-foreground">
              {r.req_tracker_no}
              {r.client_name ? ` · ${r.client_name}` : ""}
            </div>
          </div>
          {r.status && (
            <Badge variant={statusVariant(r.status)} className="shrink-0">
              {r.status}
            </Badge>
          )}
        </div>
        <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>Recruiter: {r.recruiter_name ?? "—"}</span>
          <span>Added {fmtDate(r.created_on)}</span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
          {open ? "Hide timeline" : "View timeline"}
          <CountChip n={appEvents.length} />
        </button>
      </div>
      {open && (
        <div className="border-t px-3 py-3">
          <TimelineList events={appEvents} />
        </div>
      )}
    </li>
  );
}

export function CandidateDrawer({ candidate, onClose }: { candidate: Candidate | null; onClose: () => void }) {
  const id = candidate?.cv_id ?? null;
  const { data, isLoading, isError } = useCandidateDetail(id);

  const { user } = useAuth();
  const canManage = user?.role.code === "REC" || user?.role.code === "ADM";
  const isAdmin = user?.role.code === "ADM";
  const clearStatus = useClearCandidateStatus();
  const untagReq = useUntagRequirement();
  const [tagOpen, setTagOpen] = useState(false);
  const activeReviews = data?.active_reviews ?? [];
  // A candidate can't be re-added to a requirement they're already under review
  // for (active review) OR already in the pipeline for (mapping).
  const taggedReqIds = [
    ...activeReviews.map((r) => r.req_id),
    ...(data?.requirement_history ?? []).map((r) => r.req_id),
  ];
  // Prefer the freshly-fetched detail (reflects a just-applied change) over the row.
  const statusName = data?.candidate.candidate_status_name ?? candidate?.candidate_status_name ?? null;
  const statusCode = data?.candidate.candidate_status_code ?? candidate?.candidate_status_code ?? null;

  // Fake/Blacklisted are terminal; the drawer is read-only for status EXCEPT an
  // Admin can remove the mark (recovery → Talent Pool). New Fake/Blacklist
  // decisions are made in the Pipeline (Verify & Update), not while browsing.
  const isFlagged = statusCode === "FAKE" || statusCode === "BLACKLISTED";

  function removeMark() {
    if (id == null) return;
    const reason = window.prompt("Remove this status? The candidate returns to the Talent Pool.\nReason (optional):");
    if (reason === null) return; // cancelled
    clearStatus.mutate(
      { id, reason: reason.trim() },
      {
        onSuccess: () => toast.success("Status removed — candidate restored to Talent Pool."),
        onError: () => toast.error("Couldn't remove the status."),
      },
    );
  }

  return (
    <Sheet open={!!candidate} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        {/* Header — identity from the clicked row + lightweight metadata not in the table */}
        <SheetHeader className="pr-10">
          <SheetTitle>{candidate?.candidate_name ?? "Candidate"}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">{candidate?.cv_serial}</span>
            {statusName && (
              <Badge variant={candidateStatusVariant(statusCode)}>{candidateStatusLabel(statusCode, statusName)}</Badge>
            )}
            {/* Fake/Blacklisted are terminal for the normal workflow — only an
                Admin can remove the mark (restores the candidate to Talent Pool). */}
            {isFlagged && isAdmin && (
              <Button variant="outline" size="sm" disabled={id == null || clearStatus.isPending} onClick={removeMark}>
                Remove {statusName}
              </Button>
            )}
            {isFlagged && !isAdmin && (
              <span className="text-xs text-muted-foreground">Only an admin can remove this status.</span>
            )}
          </SheetDescription>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>Created {fmtDate(candidate?.created_on ?? null)}</span>
            {candidate?.uploaded_by_name && <span>by {candidate.uploaded_by_name}</span>}
            {data && <span>{data.timeline.length} activities</span>}
            {data && <span>{data.requirement_history.length} mappings</span>}
            {data?.candidate?.date_of_birth && <span>DOB {fmtDate(data.candidate.date_of_birth)}</span>}
            {data?.candidate?.age_at_import != null && <span>Age {data.candidate.age_at_import} (as imported)</span>}
            {data?.candidate?.postal_address && <span>{data.candidate.postal_address}</span>}
            {data?.candidate?.current_location_text && !data.candidate.current_location && (
              <span className="text-orange">Location (unmapped): {data.candidate.current_location_text}</span>
            )}
            {data?.candidate?.profile_verified ? (
              <span className="inline-flex items-center gap-1 text-success">
                <ShieldCheck className="h-3 w-3" /> Verified
                {data.candidate.profile_verified_by_name ? ` by ${data.candidate.profile_verified_by_name}` : ""}
                {data.candidate.profile_verified_on ? ` · ${fmtDate(data.candidate.profile_verified_on)}` : ""}
              </span>
            ) : (
              data && <span>Profile not verified</span>
            )}
          </div>
        </SheetHeader>

        <SheetBody className="space-y-3 py-4">
          {isError ? (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" /> Couldn't load candidate details. Please try again.
            </div>
          ) : isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-11 w-full rounded-lg" />
              <Skeleton className="h-11 w-full rounded-lg" />
              <Skeleton className="h-11 w-full rounded-lg" />
            </div>
          ) : (
            <>
              {/* Activity timeline — the primary, growing content (expanded) */}
              <CollapsibleSection
                icon={Clock}
                title="Activity timeline"
                defaultOpen
                meta={<CountChip n={data?.timeline.length ?? 0} />}
              >
                <TimelineList events={data?.timeline ?? []} showReq />
              </CollapsibleSection>

              {/* Under review (pre-pipeline Review Pool — separate from the pipeline) */}
              <CollapsibleSection
                icon={Briefcase}
                title="Under review for"
                meta={<CountChip n={activeReviews.length} />}
              >
                {activeReviews.length > 0 ? (
                  <ul className="space-y-2">
                    {activeReviews.map((rv) => (
                      <li key={rv.review_id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{rv.jd_role_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {rv.req_tracker_no}{rv.client_name ? ` · ${rv.client_name}` : ""}
                          </div>
                        </div>
                        {canManage && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            disabled={untagReq.isPending || id == null}
                            onClick={() =>
                              id != null &&
                              untagReq.mutate(
                                { id, requirement: rv.req_id },
                                {
                                  onSuccess: () => toast.success(`Removed from ${rv.req_tracker_no}'s review pool.`),
                                  onError: (e: any) =>
                                    toast.error(apiErrorMessage(e, "Could not remove from the review pool.")),
                                },
                              )
                            }
                          >
                            Remove
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">Not under review for any requirement.</p>
                )}
              </CollapsibleSection>

              {/* Requirement history (collapsed) */}
              <CollapsibleSection
                icon={Briefcase}
                title="Requirement history"
                meta={<CountChip n={data?.requirement_history.length ?? 0} />}
              >
                {data && data.requirement_history.length > 0 ? (
                  <ul className="space-y-2">
                    {data.requirement_history.map((r) => (
                      <RequirementCard key={r.mapping_id} r={r} events={data.timeline} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">This candidate has not yet been mapped to any requirement.</p>
                )}
              </CollapsibleSection>
            </>
          )}
        </SheetBody>

        <SheetFooter>
          {canManage && (
            <Button variant="outline" size="sm" onClick={() => setTagOpen(true)} disabled={id == null}>
              <Tag className="h-4 w-4" /> Add to Review Pool
            </Button>
          )}
          <SheetClose asChild>
            <Button variant="ghost" size="sm" className="ml-auto">
              Close
            </Button>
          </SheetClose>
        </SheetFooter>
      </SheetContent>

      <TagToRequirementDialog
        candidate={data?.candidate ?? candidate}
        alreadyTaggedReqIds={taggedReqIds}
        open={tagOpen}
        onOpenChange={setTagOpen}
      />
    </Sheet>
  );
}
