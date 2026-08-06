import { AlertTriangle } from "lucide-react";
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
import { useCreateDuplicateReview } from "./api";

export interface DuplicateInfo {
  reason: string;
  existing_candidate: {
    cv_id: number;
    cv_serial: string;
    candidate_name: string;
    mobile: string;
    email: string;
    current_company: string | null;
  };
  submitted: {
    candidate_name: string;
    mobile: string;
    email: string;
    current_company: string | null;
  };
}

function Row({ label, a, b, differ }: { label: string; a: string | null; b: string | null; differ?: boolean }) {
  return (
    <div className="grid grid-cols-[7rem_1fr_1fr] gap-2 py-1 text-sm">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={differ ? "font-medium text-amber-700 dark:text-amber-300" : ""}>{a || "—"}</span>
      <span className={differ ? "font-medium text-amber-700 dark:text-amber-300" : ""}>{b || "—"}</span>
    </div>
  );
}

/** Shown when candidate creation hits a possible duplicate (409). Read-only
 *  side-by-side comparison — the recruiter cannot merge or edit identity here;
 *  they can only submit it for Admin review or cancel. */
export function DuplicateDetectedDialog({
  info,
  onCancel,
  onSubmitted,
}: {
  info: DuplicateInfo | null;
  onCancel: () => void;
  onSubmitted: () => void;
}) {
  const create = useCreateDuplicateReview();
  if (!info) return null;
  const { existing_candidate: ex, submitted: sub, reason } = info;

  function submit() {
    create.mutate(
      {
        existing_candidate: ex.cv_id,
        new_candidate_name: sub.candidate_name,
        new_mobile: sub.mobile,
        new_email: sub.email,
        detection_reason: reason,
        submitted_payload: sub,
      },
      {
        onSuccess: () => {
          toast.success("Submitted for Admin review.");
          onSubmitted();
        },
        onError: () => toast.error("Couldn't submit for review."),
      },
    );
  }

  return (
    <Dialog open={!!info} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" /> Possible duplicate candidate
          </DialogTitle>
          <DialogDescription>
            {reason} Identity fields can't be edited here — submit for Admin review, or cancel.
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="grid grid-cols-[7rem_1fr_1fr] gap-2 border-b pb-1 text-xs font-medium text-muted-foreground">
            <span></span>
            <span>New (being added)</span>
            <span>Existing · {ex.cv_serial}</span>
          </div>
          <Row label="Name" a={sub.candidate_name} b={ex.candidate_name} />
          <Row label="Mobile" a={sub.mobile} b={ex.mobile} differ={sub.mobile === ex.mobile ? false : true} />
          <Row label="Email" a={sub.email} b={ex.email} differ={sub.email !== ex.email} />
          <Row label="Company" a={sub.current_company} b={ex.current_company} />
          <p className="mt-3 text-xs text-muted-foreground">
            The mobile matches an existing candidate but the email differs. Nothing has been created or changed.
          </p>
        </DialogBody>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={submit} disabled={create.isPending}>
            {create.isPending ? "Submitting…" : "Submit for Admin review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
