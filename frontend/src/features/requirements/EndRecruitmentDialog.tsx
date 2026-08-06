import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/apiError";
import { useEndRecruitment } from "./api";
import type { Requirement } from "./types";

/**
 * Confirms the permanent End-Recruitment decision for an expired, partially-filled
 * requirement. Summarises the impact (open seats withdrawn + active applications
 * closed) and makes the irreversibility explicit before calling the HM-only action.
 */
export function EndRecruitmentDialog({
  requirement,
  onClose,
}: {
  requirement: Requirement | null;
  onClose: () => void;
}) {
  const endRecruitment = useEndRecruitment();
  const [reason, setReason] = useState("");

  const openSeats = requirement?.position_counts.open ?? 0;
  const activeApps = requirement?.active_application_count ?? 0;

  function close() {
    setReason("");
    onClose();
  }

  async function onConfirm() {
    if (!requirement) return;
    try {
      const data: any = await endRecruitment.mutateAsync({
        reqId: requirement.req_id,
        reason: reason.trim() || undefined,
      });
      toast.success(`Recruitment ended — ${data?.applications_closed ?? 0} application(s) closed.`);
      close();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Couldn't end recruitment."));
    }
  }

  return (
    <Dialog open={!!requirement} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>End recruitment</DialogTitle>
          <DialogDescription>
            {requirement ? `${requirement.req_tracker_no} · ${requirement.jd_role_name}` : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>This action is permanent and cannot be undone.</span>
          </div>
          <ul className="space-y-1.5 text-sm">
            <li>
              <span className="font-medium tabular-nums">{openSeats}</span> remaining open position
              {openSeats === 1 ? "" : "s"} will be withdrawn (marked <span className="font-medium">Inactive</span>).
            </li>
            <li>
              <span className="font-medium tabular-nums">{activeApps}</span> active application
              {activeApps === 1 ? "" : "s"} will be closed and eligible candidates returned to the{" "}
              <span className="font-medium">Talent Pool</span>.
            </li>
            <li>
              Filled positions and the requirement’s full history are preserved; the status stays{" "}
              <span className="font-medium">Partial Filled</span>.
            </li>
          </ul>
          <div className="space-y-1.5">
            <Label htmlFor="end-reason">Reason (optional)</Label>
            <Input
              id="end-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Budget withdrawn for the remaining seats"
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={close} disabled={endRecruitment.isPending}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={endRecruitment.isPending}>
            {endRecruitment.isPending ? "Ending…" : "End recruitment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
