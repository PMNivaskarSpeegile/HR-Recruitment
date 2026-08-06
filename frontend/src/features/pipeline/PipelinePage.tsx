import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { statusVariant } from "@/lib/status";
import { useDebounced } from "@/lib/useDebounced";
import { RequirementSelect } from "@/features/requirements/RequirementSelect";
import { PositionsPanel } from "@/features/requirements/PositionsPanel";
import type { Requirement } from "@/features/requirements/types";
import type { Candidate } from "@/features/candidates/types";
import { VerifyProfileDialog } from "@/features/candidates/VerifyProfileDialog";
import { NEW_CV_PAGE_SIZE, useNewCvs } from "./api";
import { buildNewCvColumns } from "./columns";
import { StageBoard } from "./StageBoard";

function RequirementSummary({ req }: { req: Requirement }) {
  return (
    <Card className="shadow-card">
      <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
        <div>
          <div className="text-xs text-muted-foreground">Role</div>
          <div className="font-medium">{req.jd_role_name}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Client</div>
          <div className="font-medium">{req.client_name}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Status</div>
          <Badge variant={statusVariant(req.req_status_name)}>{req.req_status_name}</Badge>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Positions</div>
          <div className="font-medium tabular-nums">
            {req.positions_filled}/{req.positions_open}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Skills</div>
          <div className="flex flex-wrap gap-1">
            {req.skill_names.length ? (
              req.skill_names.map((s) => (
                <Badge key={s} variant="muted">
                  {s}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">—</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function PipelinePage() {
  // Requirement is chosen via a server-backed searchable picker (role-scoped on
  // the backend → recruiters only get their assigned requirements), so it scales
  // past the old 100-row cap. We keep the chosen row for the summary/positions.
  const [reqId, setReqId] = useState("");
  const [selectedReq, setSelectedReq] = useState<Requirement | null>(null);

  // Server-side paginated + searched review pool (scales as the repo grows).
  const [poolPage, setPoolPage] = useState(1);
  const [poolSearch, setPoolSearch] = useState("");
  const poolSearchDebounced = useDebounced(poolSearch.trim(), 300);
  useEffect(() => setPoolPage(1), [reqId, poolSearchDebounced]); // reset to first page on req/search change

  const newCvs = useNewCvs(reqId || null, poolPage, poolSearchDebounced);
  // Verify & Update is the single entry point: verify the profile AND make the
  // decision (Shortlist / Not Suitable / Fake / Blacklist / Save) in one step,
  // in the context of this requirement. Only Shortlist enters the pipeline.
  const [verifyCandidate, setVerifyCandidate] = useState<Candidate | null>(null);

  const columns = buildNewCvColumns({ onVerify: setVerifyCandidate });

  return (
    <div>
      <PageHeader title="Pipeline" description="Review and screen candidates for your requirements" />

      <div className="mb-5 max-w-md">
        <Label className="mb-1.5 block">Requirement</Label>
        <RequirementSelect
          value={reqId}
          onChange={(id, req) => {
            setReqId(id);
            setSelectedReq(req);
          }}
          placeholder="Select an assigned requirement"
        />
      </div>

      {!reqId ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">
          Select a requirement to review its skill-matched candidates.
        </div>
      ) : (
        <div className="space-y-6">
          {selectedReq && <RequirementSummary req={selectedReq} />}
          {selectedReq && <PositionsPanel req={selectedReq} />}
          <div>
            <h2 className="mb-2 text-lg font-semibold">Candidates to review</h2>
            <DataTable
              columns={columns}
              data={newCvs.data?.results ?? []}
              isLoading={newCvs.isLoading}
              searchPlaceholder="Search candidates…"
              emptyMessage="No candidates available to add to this requirement."
              search={{ value: poolSearch, onChange: setPoolSearch }}
              serverPagination={{
                pageIndex: poolPage - 1,
                pageSize: NEW_CV_PAGE_SIZE,
                total: newCvs.data?.count ?? 0,
                onPageChange: (i) => setPoolPage(i + 1),
              }}
            />
          </div>
          <StageBoard reqId={reqId} />
        </div>
      )}

      <VerifyProfileDialog
        candidate={verifyCandidate}
        requirementId={reqId ? Number(reqId) : null}
        open={!!verifyCandidate}
        onOpenChange={(o) => !o && setVerifyCandidate(null)}
      />
    </div>
  );
}
