import { useState } from "react";
import { toast } from "sonner";
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
import { fmtDate } from "@/lib/format";
import { useUpdateRequirement } from "./api";
import type { Requirement } from "./types";

/** Today (local) as an ISO yyyy-mm-dd string, for the date input's `min`. */
function todayIso() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10);
}

/**
 * Extend an expired requirement's Target Fill Date. Setting a future date clears
 * the Expired overlay and immediately resumes normal recruitment — without
 * touching seats or applications. Not available once recruitment has ended.
 */
export function ExtendDateDialog({
  requirement,
  onClose,
}: {
  requirement: Requirement | null;
  onClose: () => void;
}) {
  const update = useUpdateRequirement();
  const [date, setDate] = useState("");
  const min = todayIso();

  function close() {
    setDate("");
    onClose();
  }

  async function onConfirm() {
    if (!requirement || !date) return;
    if (date < min) {
      toast.error("Choose a future date to resume recruitment.");
      return;
    }
    try {
      await update.mutateAsync({ reqId: requirement.req_id, payload: { target_fill_date: date } });
      toast.success("Target Fill Date extended — recruitment resumed.");
      close();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Couldn't extend the Target Fill Date."));
    }
  }

  return (
    <Dialog open={!!requirement} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Extend target fill date</DialogTitle>
          <DialogDescription>
            {requirement ? `${requirement.req_tracker_no} · ${requirement.jd_role_name}` : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-3">
          <p className="text-sm text-muted-foreground">
            This requirement expired
            {requirement?.expired_on ? ` on ${fmtDate(requirement.expired_on)}` : ""}. Setting a new
            future date resumes recruitment immediately — seats and applications are unchanged.
          </p>
          <div className="space-y-1.5">
            <Label htmlFor="extend-date">New target fill date</Label>
            <Input
              id="extend-date"
              type="date"
              min={min}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={close} disabled={update.isPending}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={!date || update.isPending}>
            {update.isPending ? "Saving…" : "Extend & resume"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
