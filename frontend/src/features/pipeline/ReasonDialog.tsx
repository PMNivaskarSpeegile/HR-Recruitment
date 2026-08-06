import { useState } from "react";
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
import { useRejectionReasons } from "@/lib/lookups";

export function ReasonDialog({
  open,
  title,
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onConfirm: (reasonId: number) => void;
}) {
  const reasons = useRejectionReasons();
  const [reason, setReason] = useState("");

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Pick a reason — it's recorded against the candidate for reporting.</DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-1.5">
          <Label>Reason</Label>
          <Select value={reason} onValueChange={setReason}>
            <SelectTrigger>
              <SelectValue placeholder="Select a reason" />
            </SelectTrigger>
            <SelectContent>
              {(reasons.data ?? []).map((r) => (
                <SelectItem key={r.reason_id} value={String(r.reason_id)}>
                  {r.reason_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!reason}
            onClick={() => {
              onConfirm(Number(reason));
              setReason("");
            }}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
