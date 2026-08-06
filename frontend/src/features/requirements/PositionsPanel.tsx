import { toast } from "sonner";
import { MoreVertical, Plus } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { positionStatusActions, positionStatusVariant } from "@/lib/status";
import { fmtDateTime } from "@/lib/format";
import { apiErrorMessage } from "@/lib/apiError";
import { useAddPositions, useDeletePosition, usePositions, useSetPositionStatus } from "./api";
import type { Position } from "./api";
import type { Requirement } from "./types";

const ADDABLE = new Set(["NEW", "ASSIGNED", "OPEN", "PARTIAL_FILLED"]);

function CountTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-card px-3 py-2">
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}

export function PositionsPanel({ req }: { req: Requirement }) {
  const { user } = useAuth();
  const role = user?.role.code;
  // Manual position status changes are Hiring-Manager-only; adding seats is HM or Admin.
  const canManage = role === "HM";
  const canAdd = role === "HM" || role === "ADM";
  const expired = req.is_expired;

  const positions = usePositions(req.req_id);
  const setStatus = useSetPositionStatus();
  const addPositions = useAddPositions();
  const deletePosition = useDeletePosition();
  const seats = positions.data ?? [];
  const c = req.position_counts;
  const canAddNow = canAdd && !expired && ADDABLE.has(req.req_status_code);

  function change(seat: Position, toStatus: string) {
    setStatus.mutate(
      { reqId: req.req_id, positionId: seat.position_id, toStatus },
      {
        onSuccess: () => toast.success(`Position ${seat.position_no} updated.`),
        onError: (e: any) => toast.error(apiErrorMessage(e, "Could not update the position.")),
      },
    );
  }

  function remove(seat: Position) {
    if (!window.confirm(`Delete Position ${seat.position_no}? This cannot be undone.`)) return;
    deletePosition.mutate(
      { reqId: req.req_id, positionId: seat.position_id },
      {
        onSuccess: () => toast.success(`Position ${seat.position_no} deleted.`),
        onError: (e: any) => toast.error(apiErrorMessage(e, "Could not delete the position.")),
      },
    );
  }

  function add() {
    const input = window.prompt("How many positions to add?", "1");
    if (input === null) return;
    const count = parseInt(input, 10);
    if (!Number.isFinite(count) || count < 1) {
      toast.error("Enter a whole number of positions to add.");
      return;
    }
    addPositions.mutate(
      { reqId: req.req_id, count },
      {
        onSuccess: () => toast.success(`Added ${count} position${count === 1 ? "" : "s"}.`),
        onError: (e: any) => toast.error(apiErrorMessage(e, "Could not add positions.")),
      },
    );
  }

  return (
    <Card className="shadow-card">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Positions</h2>
          {canAddNow && (
            <Button size="sm" variant="outline" onClick={add} disabled={addPositions.isPending}>
              <Plus className="h-4 w-4" /> Add positions
            </Button>
          )}
        </div>

        {/* Seat status breakdown */}
        <div className="mb-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
          <CountTile label="Total" value={c?.total ?? 0} />
          <CountTile label="Open" value={c?.open ?? 0} />
          <CountTile label="Filled" value={c?.filled ?? 0} />
          <CountTile label="Held" value={c?.held ?? 0} />
          <CountTile label="Cancelled" value={c?.cancelled ?? 0} />
          <CountTile label="Inactive" value={c?.inactive ?? 0} />
        </div>

        {expired && (
          <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            This requirement has expired — positions are read-only until the Target Fill Date is extended.
          </p>
        )}

        {positions.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading positions…</p>
        ) : seats.length === 0 ? (
          <p className="text-sm text-muted-foreground">No positions for this requirement yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Position</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Assigned candidate</th>
                  <th className="py-2 pr-3 font-medium">Last updated</th>
                  {canManage && <th className="py-2 text-right font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y">
                {seats.map((seat) => {
                  const statusActions = canManage && !expired ? positionStatusActions(seat.position_status_code) : [];
                  const canDelete =
                    canManage && !expired && seat.position_status_code !== "FILLED" && !seat.filled_by_mapping;
                  return (
                    <tr key={seat.position_id}>
                      <td className="py-2 pr-3 font-medium tabular-nums">Position {seat.position_no}</td>
                      <td className="py-2 pr-3">
                        <span className="inline-flex items-center gap-1.5">
                          <Badge variant={positionStatusVariant(seat.position_status_code)}>
                            {seat.position_status_name ?? "—"}
                          </Badge>
                          {seat.auto_inactive && (
                            <span className="text-[11px] text-muted-foreground">system</span>
                          )}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">{seat.filled_by_candidate ?? "—"}</td>
                      <td className="py-2 pr-3 text-muted-foreground">{fmtDateTime(seat.updated_on ?? seat.created_on)}</td>
                      {canManage && (
                        <td className="py-2 text-right">
                          {statusActions.length > 0 || canDelete ? (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost" aria-label="Position actions">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {statusActions.map((a) => (
                                  <DropdownMenuItem
                                    key={a.to + a.label}
                                    onSelect={() => change(seat, a.to)}
                                    className={a.danger ? "text-destructive focus:text-destructive" : undefined}
                                  >
                                    {a.label}
                                  </DropdownMenuItem>
                                ))}
                                {canDelete && (
                                  <>
                                    {statusActions.length > 0 && <DropdownMenuSeparator />}
                                    <DropdownMenuItem
                                      onSelect={() => remove(seat)}
                                      className="text-destructive focus:text-destructive"
                                    >
                                      Delete position
                                    </DropdownMenuItem>
                                  </>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          A position becomes <span className="font-medium">Filled</span> automatically when its candidate joins.
          <span className="font-medium"> Inactive</span> seats are set by the system when the requirement is Held or
          Cancelled, and reopen automatically when it resumes.
        </p>
      </CardContent>
    </Card>
  );
}
