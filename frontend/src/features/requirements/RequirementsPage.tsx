import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiErrorMessage } from "@/lib/apiError";
import { useDebounced } from "@/lib/useDebounced";
import { REQUIREMENTS_PAGE_SIZE, useRequirements, useSetRequirementStatus } from "./api";
import { buildRequirementColumns } from "./columns";
import { RequirementFormDialog } from "./RequirementFormDialog";
import { AssignDialog } from "./AssignDialog";
import { EndRecruitmentDialog } from "./EndRecruitmentDialog";
import { ExtendDateDialog } from "./ExtendDateDialog";
import type { Requirement } from "./types";

// Manual transitions that require a mandatory reason (mirrors the backend).
const REASON_REQUIRED = new Set(["HOLD", "CANCELLED", "CLOSE_LOST"]);
const ACTION_VERB: Record<string, string> = {
  HOLD: "put on hold", CANCELLED: "cancel", CLOSE_LOST: "close as lost",
};

/** Human label for the active deep-link filter (shown as a dismissible chip). */
function describeFilter(status: string | null, missing: string | null, q: string | null): string | null {
  if (missing === "recruiter") return "Without a recruiter";
  if (missing === "hm") return "Without a hiring manager";
  if (status === "active") return "Active requirements";
  if (status) return `Status: ${status.replace(/_/g, " ").toLowerCase()}`;
  // A `q` deep-link (e.g. the dashboard "open this requirement" links) is also a
  // filter — describe it so the chip, clear button, count and correct empty
  // message all render instead of silently showing a 1-row / empty page.
  if (q) return `Search: "${q}"`;
  return null;
}

export default function RequirementsPage() {
  const { user } = useAuth();
  // RBAC (mirrors backend): Admin → View + Assign; HM → View + Edit + lifecycle;
  // Recruiter → View only. Create/New stays HM+Admin (unchanged).
  const role = user?.role.code;
  const isAdmin = role === "ADM";
  const isHM = role === "HM";
  const canCreate = isAdmin || isHM;

  const navigate = useNavigate();
  const openDetails = (r: Requirement) => navigate(`/requirements/${r.req_id}`);

  const [createOpen, setCreateOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState<Requirement | null>(null);
  const [editTarget, setEditTarget] = useState<Requirement | null>(null);

  const [endTarget, setEndTarget] = useState<Requirement | null>(null);
  function handleEndRecruitment(r: Requirement) {
    setEndTarget(r);
  }

  const [extendTarget, setExtendTarget] = useState<Requirement | null>(null);
  function handleExtendDate(r: Requirement) {
    setExtendTarget(r);
  }

  const setStatus = useSetRequirementStatus();
  function handleSetStatus(r: Requirement, toStatus: string) {
    let reason: string | undefined;
    if (REASON_REQUIRED.has(toStatus)) {
      const input = window.prompt(`Reason to ${ACTION_VERB[toStatus]} ${r.req_tracker_no} (required):`);
      if (input === null) return; // cancelled the prompt
      if (!input.trim()) {
        toast.error("A reason is required.");
        return;
      }
      reason = input.trim();
    }
    setStatus.mutate(
      { reqId: r.req_id, toStatus, reason },
      {
        onSuccess: () => toast.success("Requirement status updated."),
        onError: (e: any) =>
          toast.error(apiErrorMessage(e, "Couldn't update the requirement status.")),
      },
    );
  }

  // Deep-link filters (e.g. from the Admin dashboard KPIs / task list). Status &
  // missing are applied SERVER-SIDE so the list + count reflect the whole
  // dataset, not just the first page.
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status");
  const missing = searchParams.get("missing");
  const q = searchParams.get("q");
  const filterLabel = describeFilter(status, missing, null); // q shows in the search box

  // Search box is seeded from a `?q=` deep-link and stays authoritative when the
  // user navigates in with a different tracker.
  const [search, setSearch] = useState(q ?? "");
  useEffect(() => setSearch(q ?? ""), [q]);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search.trim(), 300);
  // Any filter/search change → back to the first page.
  useEffect(() => setPage(1), [debouncedSearch, status, missing]);

  const { data, isLoading, isError } = useRequirements({
    page,
    search: debouncedSearch,
    status,
    missing,
  });
  const rows = data?.results ?? [];
  const total = data?.count ?? 0;

  const columnOpts = isAdmin
    ? { onView: openDetails, onAssign: setAssignTarget } // Admin: View + Assign only
    : isHM
      ? {
          onView: openDetails,
          onEdit: setEditTarget,
          onSetStatus: handleSetStatus,
          onEndRecruitment: handleEndRecruitment, // expired + partially filled
          onExtendDate: handleExtendDate, // expired (restores recruitment)
        } // HM: View + Edit + lifecycle
      : { onView: openDetails }; // Recruiter (read-only): Eye button → details page
  const columns = buildRequirementColumns(columnOpts);

  return (
    <div>
      <PageHeader title="Requirements" description="Job requisitions across all clients" />

      {isError && (
        <p className="mb-3 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Could not load requirements. Is the backend running?
        </p>
      )}

      {filterLabel && (
        <div className="mb-3 flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Filtered:</span>
          <Badge variant="secondary" className="gap-1">
            {filterLabel}
            <button
              type="button"
              aria-label="Clear filter"
              onClick={() => setSearchParams({}, { replace: true })}
              className="ml-1 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        isLoading={isLoading}
        onRowClick={openDetails}
        searchPlaceholder="Search by role, tracker or client…"
        emptyMessage={filterLabel || debouncedSearch ? "No requirements match this filter." : "No requirements yet."}
        serverPagination={{
          pageIndex: page - 1,
          pageSize: REQUIREMENTS_PAGE_SIZE,
          total,
          onPageChange: (i) => setPage(i + 1),
        }}
        search={{ value: search, onChange: setSearch }}
        toolbar={
          canCreate ? (
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              New requirement
            </Button>
          ) : undefined
        }
      />

      {canCreate && <RequirementFormDialog open={createOpen} onOpenChange={setCreateOpen} />}
      {isHM && (
        <RequirementFormDialog
          open={!!editTarget}
          onOpenChange={(o) => !o && setEditTarget(null)}
          requirement={editTarget}
        />
      )}
      {isAdmin && <AssignDialog requirement={assignTarget} onClose={() => setAssignTarget(null)} />}
      {isHM && <EndRecruitmentDialog requirement={endTarget} onClose={() => setEndTarget(null)} />}
      {isHM && <ExtendDateDialog requirement={extendTarget} onClose={() => setExtendTarget(null)} />}
    </div>
  );
}
