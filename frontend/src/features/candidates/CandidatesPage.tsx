import { useState } from "react";
import { Plus, Upload, History, MapPin } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDebounced } from "@/lib/useDebounced";
import { SkillMultiSelect } from "@/components/form/SkillMultiSelect";
import { RequirementSelect } from "@/features/requirements/RequirementSelect";
import { CANDIDATES_PAGE_SIZE, useCandidates } from "./api";
import { candidateColumns } from "./columns";
import { CandidateFormDialog } from "./CandidateFormDialog";
import { BulkUploadDialog } from "./BulkUploadDialog";
import { ImportHistoryDialog } from "./ImportHistoryDialog";
import { UnmappedLocationsDialog } from "./UnmappedLocationsDialog";
import { CandidateDrawer } from "./CandidateDrawer";
import type { Candidate } from "./types";

export default function CandidatesPage() {
  const { user } = useAuth();
  const canManage = user?.role.code === "REC" || user?.role.code === "ADM";
  // Hiring Managers get a read-only sourcing view (trimmed status options).
  const isHM = user?.role.code === "HM";

  // "ACTIVE" = default Candidate Database view (hides Reject-Hold/Joined/Fake/
  // Blacklisted); "ALL" = every candidate; a code = that status only.
  const [statusFilter, setStatusFilter] = useState("ACTIVE");
  // Requirement filter (all roles): a selected requirement shows ONLY the
  // candidates mapped to it. The list is role-scoped server-side (Admin: all;
  // Recruiter: assigned; HM: owned).
  const [reqFilter, setReqFilter] = useState("all");
  const [skillIds, setSkillIds] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search.trim(), 300);
  // Any filter/search change → back to page 1. Computed during render (React's
  // recommended "adjusting state when a prop changes" pattern) instead of a
  // useEffect, so this doesn't cause an extra cascading render.
  const filterKey = `${statusFilter}|${reqFilter}|${debouncedSearch}|${skillIds.join(",")}`;
  const [prevFilterKey, setPrevFilterKey] = useState(filterKey);
  if (filterKey !== prevFilterKey) {
    setPrevFilterKey(filterKey);
    setPage(1);
  }

  const { data, isLoading, isError } = useCandidates(
    statusFilter === "ACTIVE" ? undefined : statusFilter,
    reqFilter !== "all" ? reqFilter : undefined,
    page,
    debouncedSearch,
    skillIds,
  );
  const [addOpen, setAddOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [unmappedOpen, setUnmappedOpen] = useState(false);
  const [selected, setSelected] = useState<Candidate | null>(null);
  // Editing an existing candidate reuses the same Add Candidate form/dialog,
  // pre-populated with this candidate's data (Administrator/Recruiter only —
  // the Edit action itself is only rendered for `canManage`).
  const [editingCandidate, setEditingCandidate] = useState<Candidate | null>(null);

  const rows = data?.results ?? [];
  const total = data?.count ?? 0;

  return (
    <div>
      <PageHeader title="Candidates" description="Your CV database" />

      {isError && (
        <p className="mb-3 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Could not load candidates. Is the backend running?
        </p>
      )}

      <DataTable<Candidate, unknown>
        columns={candidateColumns(canManage ? { onEdit: (c) => setEditingCandidate(c) } : undefined)}
        data={rows}
        isLoading={isLoading}
        searchPlaceholder="Search by name, mobile, email or location…"
        emptyMessage={debouncedSearch || reqFilter !== "all" || statusFilter !== "ACTIVE" || skillIds.length
          ? "No candidates match this filter."
          : "No candidates yet."}
        serverPagination={{
          pageIndex: page - 1,
          pageSize: CANDIDATES_PAGE_SIZE,
          total,
          onPageChange: (i) => setPage(i + 1),
        }}
        search={{ value: search, onChange: setSearch }}
        onRowClick={setSelected}
        toolbar={
          <>
            <div className="w-60">
              <RequirementSelect
                value={reqFilter === "all" ? "" : reqFilter}
                onChange={(id) => setReqFilter(id || "all")}
                clearable
                clearLabel="All requirements"
                placeholder="All requirements"
              />
            </div>
            <div className="w-60">
              <SkillMultiSelect
                value={skillIds}
                onChange={setSkillIds}
                allowCreate={false}
                placeholder="Filter by skills…"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {isHM ? (
                  <>
                    <SelectItem value="ACTIVE">All visible</SelectItem>
                    <SelectItem value="NEW_CV">New CV</SelectItem>
                    <SelectItem value="SAVED">Talent Pool</SelectItem>
                  </>
                ) : (
                  <>
                    <SelectItem value="ACTIVE">Active candidates</SelectItem>
                    <SelectItem value="ALL">All candidates</SelectItem>
                    <SelectItem value="NEW_CV">New CV</SelectItem>
                    <SelectItem value="SAVED">Talent Pool</SelectItem>
                    <SelectItem value="REJECT_HOLD">Reject Hold</SelectItem>
                    <SelectItem value="JOINED">Joined</SelectItem>
                    <SelectItem value="FAKE">Fake</SelectItem>
                    <SelectItem value="BLACKLISTED">Blacklisted</SelectItem>
                  </>
                )}
              </SelectContent>
            </Select>
            {canManage && (
              <>
                <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
                  <Upload className="h-4 w-4" />
                  Bulk upload
                </Button>
                <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)}>
                  <History className="h-4 w-4" />
                  Import history
                </Button>
                <Button variant="outline" size="sm" onClick={() => setUnmappedOpen(true)}>
                  <MapPin className="h-4 w-4" />
                  Unmapped locations
                </Button>
                <Button size="sm" onClick={() => setAddOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Add candidate
                </Button>
              </>
            )}
          </>
        }
      />

      {canManage && (
        <CandidateFormDialog
          open={addOpen || editingCandidate !== null}
          onOpenChange={(o) => {
            if (!o) {
              setAddOpen(false);
              setEditingCandidate(null);
            }
          }}
          candidate={editingCandidate}
        />
      )}
      {canManage && <BulkUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />}
      {canManage && <ImportHistoryDialog open={historyOpen} onOpenChange={setHistoryOpen} />}
      {canManage && <UnmappedLocationsDialog open={unmappedOpen} onOpenChange={setUnmappedOpen} />}
      <CandidateDrawer candidate={selected} onClose={() => setSelected(null)} />
    </div>
  );
}