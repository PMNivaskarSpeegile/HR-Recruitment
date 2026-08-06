import { useState } from "react";
import { toast } from "sonner";
import { Phone, Video, CheckCircle2, Clock } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDateTime } from "@/lib/format";
import { apiErrorMessage } from "@/lib/apiError";
import { actionLabel } from "@/lib/workflow";
import { useScreeningModes } from "@/lib/lookups";
import {
  useScreenings,
  useScheduleScreening,
  useRecordOutcome,
  useRescheduleScreeningRound,
} from "./api";
import type { Screening } from "./api";
import type { Mapping } from "./types";

/** The current local minute for a datetime-local `min`. Floors the picker at
 *  "now": today stays fully selectable for any UPCOMING time, while already-
 *  passed times (and past dates) are greyed out — so a recruiter can't pick a
 *  time that's already elapsed. Recomputed on each call so it never goes stale.
 *  The submit guards + backend enforce the same rule as a backstop. */
const localNowFloor = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

// Interviewer name: letters + spaces only (no digits / symbols), stored Title Case.
const sanitizeInterviewer = (v: string) => v.replace(/[^A-Za-z ]/g, "");
const toTitleCase = (v: string) =>
  v.split(/\s+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" ");

// Screening-round outcomes — kept only to label historical completed rounds in
// the history list (recording now sets an APPLICATION outcome, see below).
const OUTCOMES = [
  { value: "PASSED", label: "Passed" },
  { value: "FAILED", label: "Failed" },
  { value: "NO_SHOW", label: "No Show" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "RESCHEDULE_REQUIRED", label: "Reschedule Required" },
];

// Record Outcome (application outcome) options for a scheduled screening.
// "OK to Proceed" advances the stage (engine outcome PASSED); the rest close the
// application. Reschedule is a separate action at the top of the popup, so it is
// intentionally NOT listed here.
const APP_OUTCOMES = ["PASSED", "NO_RESPONSE", "DROPPED", "REJECTED", "FAKE", "BLACKLISTED"].map((value) => ({
  value,
  label: actionLabel(value),
}));
// Non-hired closes that offer the opt-in "Move to Talent Pool?" prompt.
const CLOSING_NONHIRED = new Set(["NO_RESPONSE", "DROPPED", "REJECTED"]);

const outcomeVariant = (o: string | null): "success" | "danger" | "warning" | "muted" => {
  if (o === "PASSED") return "success";
  if (o === "FAILED") return "danger";
  if (o === "CANCELLED") return "muted";
  return "warning"; // NO_SHOW / RESCHEDULE_REQUIRED
};

const outcomeLabel = (o: string | null) => OUTCOMES.find((x) => x.value === o)?.label ?? o ?? "";
const apiError = apiErrorMessage;

function ModeIcon({ code }: { code: string }) {
  if (code === "TELEPHONIC") return <Phone className="h-4 w-4 text-muted-foreground" />;
  if (code === "VIDEO") return <Video className="h-4 w-4 text-muted-foreground" />;
  return <CheckCircle2 className="h-4 w-4 text-muted-foreground" />;
}

/** A completed round in the history, or the open round with an inline
 *  reschedule action + Record Outcome (application outcome) form. */
function ScreeningRow({
  s,
  onRecordOutcome,
  recording,
  canManage,
}: {
  s: Screening;
  onRecordOutcome: (outcome: string, notes: string) => void;
  recording: boolean;
  // Reschedule + Record Outcome are available ONLY in the Screening Scheduled
  // stage. Right after scheduling from JD Email Sent, the dialog closes and this
  // is false, so the outcome form never appears in the JD Email Sent context.
  canManage: boolean;
}) {
  const reschedule = useRescheduleScreeningRound();
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [rescheduling, setRescheduling] = useState(false);
  const [newDt, setNewDt] = useState("");

  const done = s.status === "COMPLETED";

  function submitReschedule() {
    if (!newDt) return;
    if (new Date(newDt).getTime() <= Date.now()) {
      toast.error("Screening must be rescheduled to a future date and time.");
      return;
    }
    reschedule.mutate(
      { id: s.screening_id, scheduled_at: new Date(newDt).toISOString() },
      {
        onSuccess: () => {
          toast.success("Screening rescheduled");
          setRescheduling(false);
          setNewDt("");
        },
        onError: (e) => toast.error(apiError(e, "Could not reschedule the screening.")),
      }
    );
  }
  return (
    <li className="space-y-2 px-1 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ModeIcon code={s.screening_mode_code} />
          <span className="text-sm font-medium">{s.screening_mode_name}</span>
          {done ? (
            <Badge variant={outcomeVariant(s.outcome)}>{outcomeLabel(s.outcome)}</Badge>
          ) : (
            <Badge variant="teal">Scheduled</Badge>
          )}
        </div>
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" /> {fmtDateTime(s.scheduled_at)}
        </span>
      </div>
      {(s.interviewer || s.notes) && (
        <div className="pl-6 text-xs text-muted-foreground">
          {s.interviewer && <div>Interviewer: {s.interviewer}</div>}
          {s.notes && <div className="whitespace-pre-wrap">{s.notes}</div>}
        </div>
      )}

      {!done && canManage && (
        <div className="ml-6 space-y-2 rounded-md border bg-muted/40 p-3">
          {/* Reschedule — move a still-scheduled round to a new future date/time */}
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-medium">Reschedule</div>
            {!rescheduling && (
              <Button variant="outline" size="sm" onClick={() => setRescheduling(true)}>
                <Clock className="h-3.5 w-3.5" /> Reschedule
              </Button>
            )}
          </div>
          {rescheduling && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1.5">
                <Label className="text-xs">New date &amp; time</Label>
                <Input
                  type="datetime-local"
                  className="w-56"
                  min={localNowFloor()}
                  value={newDt}
                  onChange={(e) => setNewDt(e.target.value)}
                />
              </div>
              <Button size="sm" disabled={!newDt || reschedule.isPending} onClick={submitReschedule}>
                Save
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setRescheduling(false);
                  setNewDt("");
                }}
              >
                Cancel
              </Button>
            </div>
          )}

          <div className="border-t pt-2 text-xs font-medium">Record outcome</div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={outcome} onValueChange={setOutcome}>
              <SelectTrigger className="h-9 w-52">
                <SelectValue placeholder="Select outcome" />
              </SelectTrigger>
              <SelectContent>
                {APP_OUTCOMES.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Textarea
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reason / notes (optional)"
          />
          <Button
            size="sm"
            disabled={!outcome || recording}
            onClick={() => onRecordOutcome(outcome, notes)}
          >
            Save outcome
          </Button>
        </div>
      )}
    </li>
  );
}

export function ScreeningDialog({ mapping, onClose }: { mapping: Mapping | null; onClose: () => void }) {
  const modes = useScreeningModes();
  const screenings = useScreenings(mapping?.mapping_id ?? null);
  const schedule = useScheduleScreening();
  const recordOutcome = useRecordOutcome();

  // Record the APPLICATION outcome from the popup. "OK to Proceed" (engine
  // outcome PASSED) advances the stage; the rest close the application and
  // update latest_outcome. Non-hired closes offer the opt-in Talent-Pool prompt.
  function handleRecordOutcome(outcome: string, reason: string) {
    if (!mapping) return;
    const move_to_talent_pool = CLOSING_NONHIRED.has(outcome)
      ? window.confirm("Move candidate to Talent Pool for future opportunities?")
      : false;
    recordOutcome.mutate(
      { mapping: mapping.mapping_id, outcome, reason: reason || undefined, move_to_talent_pool },
      {
        onSuccess: () => {
          toast.success("Outcome recorded");
          onClose();
        },
        onError: (e) => toast.error(apiError(e, "Could not record the outcome.")),
      }
    );
  }

  const [modeId, setModeId] = useState("");
  const [dt, setDt] = useState("");
  const [interviewer, setInterviewer] = useState("");
  const [notes, setNotes] = useState("");

  const rows = screenings.data ?? [];
  const hasOpen = rows.some((s) => s.status === "SCHEDULED");
  // Outcome recording + rescheduling are allowed ONLY in the Screening Scheduled
  // stage (item 6). Scheduling from JD Email Sent advances the stage and closes
  // this dialog, so the outcome form never shows in the JD Email Sent context.
  const canManage = mapping?.application_stage_code === "SCREENING_SCHEDULED";
  const interviewerValid = interviewer.trim().length > 0;

  function resetForm() {
    setModeId("");
    setDt("");
    setInterviewer("");
    setNotes("");
  }

  function add() {
    if (!mapping || !modeId || !dt) return;
    if (!interviewerValid) {
      toast.error("Interviewer is required.");
      return;
    }
    if (new Date(dt).getTime() <= Date.now()) {
      toast.error("Screening must be scheduled for a future date and time.");
      return;
    }
    schedule.mutate(
      {
        mapping: mapping.mapping_id,
        screening_mode: Number(modeId),
        scheduled_at: new Date(dt).toISOString(),
        interviewer: toTitleCase(interviewer),
        notes: notes || undefined,
      },
      {
        onSuccess: () => {
          // Scheduling advances the candidate to Screening Scheduled — close the
          // dialog here (item 6). Outcome recording / rescheduling happen by
          // reopening Screenings from the Screening Scheduled stage.
          toast.success("Screening scheduled");
          resetForm();
          onClose();
        },
        onError: (e) => toast.error(apiError(e, "Could not schedule the screening.")),
      }
    );
  }

  return (
    <Dialog open={!!mapping} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Screenings</DialogTitle>
          <DialogDescription>{mapping ? `${mapping.cv_serial} · ${mapping.candidate_name}` : ""}</DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          {/* History */}
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Screening history</div>
            {screenings.isLoading ? (
              <p className="py-4 text-sm text-muted-foreground">Loading…</p>
            ) : rows.length === 0 ? (
              <p className="rounded-md border border-dashed py-6 text-center text-sm text-muted-foreground">
                No screenings yet. Add the first round below.
              </p>
            ) : (
              <ul className="divide-y">
                {rows.map((s) => (
                  <ScreeningRow
                    key={s.screening_id}
                    s={s}
                    onRecordOutcome={handleRecordOutcome}
                    recording={recordOutcome.isPending}
                    canManage={canManage}
                  />
                ))}
              </ul>
            )}
          </div>

          {/* Add screening */}
          <div className="space-y-3 rounded-md border p-3">
            <div className="text-sm font-medium">Add screening</div>
            {hasOpen ? (
              <p className="text-xs text-muted-foreground">
                Record the outcome of the current screening before scheduling another.
              </p>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Type</Label>
                    <Select value={modeId} onValueChange={setModeId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Telephonic / Video" />
                      </SelectTrigger>
                      <SelectContent>
                        {(modes.data ?? []).map((m) => (
                          <SelectItem key={m.screening_mode_id} value={String(m.screening_mode_id)}>
                            {m.mode_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Date &amp; time</Label>
                    <Input type="datetime-local" min={localNowFloor()} value={dt} onChange={(e) => setDt(e.target.value)} />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Interviewer <span className="text-destructive">*</span></Label>
                  <Input
                    value={interviewer}
                    onChange={(e) => setInterviewer(sanitizeInterviewer(e.target.value))}
                    onBlur={() => setInterviewer((v) => toTitleCase(v))}
                    placeholder="Name (letters only)"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Notes</Label>
                  <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" />
                </div>
                <Button size="sm" disabled={!modeId || !dt || !interviewerValid || schedule.isPending} onClick={add}>
                  {actionLabel("SCHEDULE_SCREENING")}
                </Button>
              </>
            )}
          </div>
        </DialogBody>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
