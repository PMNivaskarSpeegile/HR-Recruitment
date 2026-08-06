import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Briefcase, Check, Search } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { statusVariant } from "@/lib/status";
import { apiErrorMessage } from "@/lib/apiError";
import { useDebounced } from "@/lib/useDebounced";
import { useRequirements } from "@/features/requirements/api";
import { useTagRequirement } from "./api";
import type { Candidate } from "./types";

// A candidate may only be tagged to a requirement that is still taking
// candidates — never a closed / cancelled / filled one (existing business rule).
const NON_TAGGABLE_STATUSES = new Set(["CANCELLED", "CLOSE_FILLED", "CLOSE_LOST", "EXPIRED"]);

export function TagToRequirementDialog({
  candidate,
  alreadyTaggedReqIds,
  open,
  onOpenChange,
}: {
  candidate: Candidate | null;
  alreadyTaggedReqIds: number[];
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounced(query.trim(), 300);
  // Server-side search (by tracker / role / client), role-scoped on the backend
  // (recruiters only see their assigned requirements) — so it finds a match
  // beyond the newest page. We only drop the non-taggable statuses from the
  // returned page here.
  const { data, isLoading, isError } = useRequirements({
    search: debouncedQuery,
    pageSize: 20,
    enabled: open,
  });
  const tagReq = useTagRequirement();
  const tagged = useMemo(() => new Set(alreadyTaggedReqIds), [alreadyTaggedReqIds]);

  const results = useMemo(
    () => (data?.results ?? []).filter((r) => !NON_TAGGABLE_STATUSES.has(r.req_status_code)),
    [data],
  );

  function tag(reqId: number, trackerNo: string) {
    if (!candidate) return;
    if (tagged.has(reqId)) {
      toast.error("This candidate is already tagged to that requirement.");
      return;
    }
    tagReq.mutate(
      { id: candidate.cv_id, requirementIds: [reqId] },
      {
        onSuccess: () => {
          toast.success(`${candidate.candidate_name} added to ${trackerNo}'s review pool.`);
          onOpenChange(false);
        },
        onError: (e: any) =>
          toast.error(apiErrorMessage(e, "Could not add the candidate to this requirement's review pool.")),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" /> Add to Review Pool
          </DialogTitle>
          <DialogDescription>
            Put <span className="font-medium">{candidate?.candidate_name}</span> under review for one of your open
            requirements. This does not shortlist them — you'll verify and decide from the review pool. Search by
            requirement ID or title.
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search requirement ID or title…"
              className="pl-9"
            />
          </div>

          {isError ? (
            <p className="py-6 text-center text-sm text-destructive">Could not load requirements.</p>
          ) : isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full rounded-md" />
              <Skeleton className="h-14 w-full rounded-md" />
              <Skeleton className="h-14 w-full rounded-md" />
            </div>
          ) : results.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No taggable requirements match your search.
            </p>
          ) : (
            <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {results.map((r) => {
                const isTagged = tagged.has(r.req_id);
                return (
                  <li key={r.req_id}>
                    <button
                      type="button"
                      disabled={isTagged || tagReq.isPending}
                      onClick={() => tag(r.req_id, r.req_tracker_no)}
                      className="flex w-full items-start justify-between gap-3 rounded-md border px-3 py-2.5 text-left transition-colors hover:bg-accent/40 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{r.jd_role_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {r.req_tracker_no}
                          {r.client_name ? ` · ${r.client_name}` : ""}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {r.req_status_name && (
                          <Badge variant={statusVariant(r.req_status_name)}>{r.req_status_name}</Badge>
                        )}
                        {isTagged && (
                          <span className="inline-flex items-center gap-1 text-xs text-success">
                            <Check className="h-3.5 w-3.5" /> Tagged
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
