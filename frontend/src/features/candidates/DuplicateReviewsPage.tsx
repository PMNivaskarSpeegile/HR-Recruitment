import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { fmtDateTime } from "@/lib/format";
import { apiErrorMessage } from "@/lib/apiError";
import { useDuplicateReviews, useResolveDuplicateReview, type DuplicateReview } from "./api";

const RESOLUTION_LABEL: Record<string, string> = {
  UPDATED: "Updated",
  KEPT_SEPARATE: "Ignored",
  // Legacy resolutions kept for historical rows.
  MERGED: "Merged",
  CORRECTED: "Corrected",
};

function CompareRow({ label, a, b, differ }: { label: string; a: string | null; b: string | null; differ?: boolean }) {
  return (
    <div className="grid grid-cols-[6rem_1fr_1fr] gap-2 py-0.5 text-sm">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={differ ? "font-medium text-amber-700 dark:text-amber-300" : ""}>{a || "—"}</span>
      <span className={differ ? "font-medium text-amber-700 dark:text-amber-300" : ""}>{b || "—"}</span>
    </div>
  );
}

// Module-level (stable identity) so typing in the Input never remounts + loses
// focus. Shows quick-pick chips for existing vs submitted when they differ.
function FieldRow({ label, submitted, existing, value, onChange }: {
  label: string;
  submitted?: string | null;
  existing?: string | null;
  value: string;
  onChange: (v: string) => void;
}) {
  const sub = (submitted ?? "").trim();
  const exi = (existing ?? "").trim();
  const differ = sub !== "" && sub !== exi;
  const chip = (v: string, tag: string) => (
    <button
      type="button"
      onClick={() => onChange(v)}
      className={cn(
        "rounded border px-2 py-1 text-xs",
        value === v ? "border-primary bg-primary/10 text-foreground" : "text-muted-foreground",
      )}
    >
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{tag}</span> {v}
    </button>
  );
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {differ && (
        <div className="flex flex-wrap gap-2">
          {chip(sub, "submitted")}
          {exi && chip(exi, "existing")}
        </div>
      )}
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

/**
 * Admin: write the chosen name/mobile/email onto the EXISTING candidate — the one
 * surviving record (the submitted row was never imported). Covers both "same
 * person → adopt the submitted info" and "fix a typo on the existing record",
 * which used to be two separate actions (Merge / Correct identity).
 */
function UpdateExistingDialog({ review, onClose }: { review: DuplicateReview | null; onClose: () => void }) {
  const resolve = useResolveDuplicateReview();
  const ex = review?.existing_candidate_detail;
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");

  // Seed each field to the EXISTING value (safe default — nothing changes unless
  // the admin adopts the submitted value or edits it) when the dialog opens.
  useEffect(() => {
    if (review) {
      setName(ex?.candidate_name ?? review.new_candidate_name ?? "");
      setMobile(ex?.mobile ?? review.new_mobile ?? "");
      setEmail(ex?.email ?? review.new_email ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review]);

  function save() {
    if (!review) return;
    resolve.mutate(
      { id: review.review_id, resolution: "UPDATED", name, mobile, email,
        notes: "Updated existing record from duplicate review" },
      {
        onSuccess: () => {
          toast.success(`Updated ${ex?.cv_serial ?? "the existing candidate"} and resolved the review.`);
          onClose();
        },
        onError: (e) => toast.error(apiErrorMessage(e, "Couldn't update the record.")),
      },
    );
  }

  return (
    <Dialog open={!!review} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update existing record</DialogTitle>
          <DialogDescription>
            Write the correct details onto the existing candidate{ex ? ` (${ex.cv_serial})` : ""}. Pick the value to keep
            where the submitted and existing differ, or edit directly. The submitted row is discarded.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="space-y-4">
            <FieldRow label="Name" submitted={review?.new_candidate_name} existing={ex?.candidate_name} value={name} onChange={setName} />
            <FieldRow label="Mobile" submitted={review?.new_mobile} existing={ex?.mobile} value={mobile} onChange={setMobile} />
            <FieldRow label="Email" submitted={review?.new_email} existing={ex?.email} value={email} onChange={setEmail} />
            <p className="text-xs text-muted-foreground">
              Only name, mobile and email are applied. Other details on the submitted row (experience, company,
              skills, etc.) are not merged — the existing profile is kept. Update those via the candidate's Verify &amp;
              Update if needed.
            </p>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={resolve.isPending}>Update &amp; resolve</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReviewCard({ r, onUpdate }: { r: DuplicateReview; onUpdate: (r: DuplicateReview) => void }) {
  const resolve = useResolveDuplicateReview();
  const ex = r.existing_candidate_detail;
  const pending = r.review_status === "PENDING";

  function ignore() {
    if (!window.confirm(`Ignore the submitted data for review #${r.review_id}? The existing record is kept unchanged.`)) return;
    resolve.mutate(
      { id: r.review_id, resolution: "KEPT_SEPARATE" },
      {
        onSuccess: () => toast.success("Submission ignored; review resolved."),
        onError: () => toast.error("Couldn't resolve the review."),
      },
    );
  }

  return (
    <Card className="shadow-card">
      <CardContent className="p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">Review #{r.review_id}</span>
            <Badge variant={pending ? "warning" : "success"}>
              {pending ? "Pending" : `Resolved · ${RESOLUTION_LABEL[r.resolution ?? ""] ?? r.resolution}`}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">{r.detection_reason}</span>
        </div>

        <div className="grid grid-cols-[6rem_1fr_1fr] gap-2 border-b pb-1 text-xs font-medium text-muted-foreground">
          <span></span>
          <span>New (submitted)</span>
          <span>Existing{ex ? ` · ${ex.cv_serial}` : ""}</span>
        </div>
        <CompareRow label="Name" a={r.new_candidate_name} b={ex?.candidate_name ?? null} />
        <CompareRow label="Mobile" a={r.new_mobile} b={ex?.mobile ?? null} differ={r.new_mobile !== (ex?.mobile ?? "")} />
        <CompareRow label="Email" a={r.new_email} b={ex?.email ?? null} differ={r.new_email !== (ex?.email ?? "")} />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            Reported by {r.created_by_name ?? "—"} · {fmtDateTime(r.created_on)}
            {!pending && (
              <> · resolved by {r.resolved_by_name ?? "—"} · {fmtDateTime(r.resolved_on)}</>
            )}
          </div>
          {pending && (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={ignore}>
                Ignore submission
              </Button>
              <Button size="sm" disabled={resolve.isPending} onClick={() => onUpdate(r)}>
                Update existing record
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DuplicateReviewsPage() {
  const [tab, setTab] = useState<"PENDING" | "RESOLVED">("PENDING");
  const { data, isLoading, isError } = useDuplicateReviews(tab);
  const [updating, setUpdating] = useState<DuplicateReview | null>(null);
  const reviews = data?.results ?? [];

  return (
    <div>
      <PageHeader title="Duplicate Review" description="Resolve detected possible-duplicate candidates. Separate from candidate status." />

      <div className="mb-3 flex gap-2">
        {(["PENDING", "RESOLVED"] as const).map((s) => (
          <Button key={s} size="sm" variant={tab === s ? "default" : "outline"} onClick={() => setTab(s)}>
            {s === "PENDING" ? "Pending" : "Resolved"}
          </Button>
        ))}
      </div>

      {isError ? (
        <p className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">Couldn't load duplicate reviews.</p>
      ) : isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40 w-full rounded-lg" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      ) : reviews.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {tab === "PENDING" ? "No pending duplicate reviews. 🎉" : "No resolved reviews yet."}
        </p>
      ) : (
        <div className="space-y-3">
          {reviews.map((r) => (
            <ReviewCard key={r.review_id} r={r} onUpdate={setUpdating} />
          ))}
        </div>
      )}

      <UpdateExistingDialog review={updating} onClose={() => setUpdating(null)} />
    </div>
  );
}
