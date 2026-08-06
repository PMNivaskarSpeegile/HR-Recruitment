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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUsers } from "@/lib/lookups";
import { apiErrorMessage } from "@/lib/apiError";
import { useAssignRequirement } from "./api";
import type { Requirement } from "./types";

export function AssignDialog({ requirement, onClose }: { requirement: Requirement | null; onClose: () => void }) {
  const users = useUsers();
  const assign = useAssignRequirement();
  const [recruiter, setRecruiter] = useState("");

  const recruiters = (users.data ?? []).filter((u) => u.role_code === "REC" && u.is_active);

  // Reset the picked recruiter whenever the dialog closes (not only on a
  // successful assign) so reopening for a different requirement starts blank.
  function handleClose() {
    setRecruiter("");
    onClose();
  }

  async function onSubmit() {
    if (!requirement || !recruiter) return;
    try {
      await assign.mutateAsync({ reqId: requirement.req_id, recruiter: Number(recruiter) });
      toast.success("Requirement assigned");
      handleClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Could not assign the requirement."));
    }
  }

  return (
    <Dialog open={!!requirement} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Assign recruiter</DialogTitle>
          <DialogDescription>
            {requirement ? `${requirement.req_tracker_no} · ${requirement.jd_role_name}` : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-1.5">
          <Label>Recruiter</Label>
          <Select value={recruiter} onValueChange={setRecruiter}>
            <SelectTrigger>
              <SelectValue placeholder="Select a recruiter" />
            </SelectTrigger>
            <SelectContent>
              {recruiters.map((r) => (
                <SelectItem key={r.user_id} value={String(r.user_id)}>
                  {r.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={!recruiter || assign.isPending}>
            {assign.isPending ? "Assigning…" : "Assign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
