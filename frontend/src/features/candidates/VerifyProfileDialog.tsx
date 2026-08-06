import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage } from "@/lib/apiError";
import { ShieldCheck } from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LocationSelect } from "@/components/form/LocationSelect";
import { SkillMultiSelect } from "@/components/form/SkillMultiSelect";
import { useNoticePeriods, useSources, useWorkModes } from "@/lib/lookups";
import { useVerifyCandidateProfile } from "./api";
import type { Candidate } from "./types";

// Master-profile edit form. Everything here updates the SINGLE candidate record
// (visible across all requirements) — never a per-requirement copy.
interface FormState {
  candidate_name: string;
  email: string;
  mobile: string;
  current_company: string;
  current_designation: string;
  highest_qualification: string;
  certifications: string;
  additional_notes: string;
  exp_min: string;
  exp_max: string;
  relevant_exp: string;
  current_ctc_lpa: string;
  expected_ctc_lpa: string;
  is_willing_to_relocate: boolean;
}

const str = (v: unknown) => (v == null ? "" : String(v));

function fromCandidate(c: Candidate): FormState {
  return {
    candidate_name: c.candidate_name ?? "",
    email: c.email ?? "",
    mobile: c.mobile ?? "",
    current_company: str(c.current_company),
    current_designation: str(c.current_designation),
    highest_qualification: str(c.highest_qualification),
    certifications: str(c.certifications),
    additional_notes: str(c.additional_notes),
    exp_min: str(c.exp_min),
    exp_max: str(c.exp_max),
    relevant_exp: str(c.relevant_exp),
    current_ctc_lpa: str(c.current_ctc_lpa),
    expected_ctc_lpa: str(c.expected_ctc_lpa),
    is_willing_to_relocate: !!c.is_willing_to_relocate,
  };
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));

export function VerifyProfileDialog({
  candidate,
  open,
  onOpenChange,
  requirementId = null,
}: {
  candidate: Candidate | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  // When opened from a requirement/pipeline context, the Shortlist / Not Suitable
  // decisions are enabled and scoped to this requirement.
  requirementId?: number | null;
}) {
  const notices = useNoticePeriods();
  const workModes = useWorkModes();
  const sources = useSources();
  const verify = useVerifyCandidateProfile();

  const [form, setForm] = useState<FormState>(() => (candidate ? fromCandidate(candidate) : ({} as FormState)));
  const [locationId, setLocationId] = useState<number | null>(null);
  const [noticeId, setNoticeId] = useState<string>("");
  const [workModeId, setWorkModeId] = useState<string>("");
  const [sourceId, setSourceId] = useState<string>("");
  const [skillIds, setSkillIds] = useState<number[]>([]);
  const [verified, setVerified] = useState(true);

  // Prefill from the master profile each time the dialog opens.
  useEffect(() => {
    if (!open || !candidate) return;
    setForm(fromCandidate(candidate));
    setLocationId(candidate.current_location ?? null);
    setNoticeId(candidate.notice_period != null ? String(candidate.notice_period) : "");
    setWorkModeId(candidate.work_mode != null ? String(candidate.work_mode) : "");
    setSourceId(candidate.source != null ? String(candidate.source) : "");
    setSkillIds(candidate.skill_ids ?? []);
    setVerified(true);
  }, [open, candidate]);

  const set = (k: keyof FormState, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  // `decision`: one of SHORTLIST / NOT_SUITABLE / FAKE / BLACKLIST / SAVE, or
  // undefined to just save the profile without a decision.
  function submit(decision?: string) {
    if (!candidate) return;
    const payload: Record<string, unknown> = {
      candidate_name: form.candidate_name,
      email: form.email,
      mobile: form.mobile,
      current_company: form.current_company || null,
      current_designation: form.current_designation || null,
      highest_qualification: form.highest_qualification || null,
      certifications: form.certifications || null,
      additional_notes: form.additional_notes || null,
      exp_min: num(form.exp_min),
      exp_max: num(form.exp_max),
      relevant_exp: num(form.relevant_exp),
      current_ctc_lpa: num(form.current_ctc_lpa),
      expected_ctc_lpa: num(form.expected_ctc_lpa),
      is_willing_to_relocate: form.is_willing_to_relocate,
      current_location: locationId,
      notice_period: noticeId ? Number(noticeId) : null,
      work_mode: workModeId ? Number(workModeId) : null,
      source: sourceId ? Number(sourceId) : null,
      skill_ids: skillIds,
      verified,
    };

    if (decision) {
      payload.decision = decision;
      if (requirementId) payload.requirement = requirementId;
      // Fake / Blacklist capture a mandatory reason. (Talent Pool is now its own
      // decision — "Save"; Not Suitable simply resolves the review, no extra prompt.)
      if (decision === "FAKE" || decision === "BLACKLIST") {
        const r = window.prompt(`Reason for marking this candidate ${decision === "FAKE" ? "Fake" : "Blacklisted"}:`);
        if (r === null) return; // cancelled
        payload.decision_reason = r.trim();
      }
    }

    verify.mutate(
      { id: candidate.cv_id, ...payload },
      {
        onSuccess: () => {
          const msg = decision
            ? "Profile updated and decision recorded."
            : "Candidate profile updated successfully. Changes will be reflected across all requirements.";
          toast.success(msg);
          onOpenChange(false);
        },
        onError: (e: any) => {
          const fallback = e?.response?.status === 409
            ? "That mobile/email belongs to another candidate."
            : "Could not update the profile. Please check the fields.";
          toast.error(apiErrorMessage(e, fallback));
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" /> Verify &amp; Update Profile
          </DialogTitle>
          <DialogDescription>
            You're editing the <span className="font-medium">master candidate profile</span> — changes apply everywhere
            this candidate appears, across all requirements.
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Full name</Label>
              <Input value={form.candidate_name} onChange={(e) => set("candidate_name", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Mobile</Label>
              <Input value={form.mobile} onChange={(e) => set("mobile", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input value={form.email} onChange={(e) => set("email", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Current company</Label>
              <Input value={form.current_company} onChange={(e) => set("current_company", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Current designation</Label>
              <Input value={form.current_designation} onChange={(e) => set("current_designation", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Current location</Label>
              <LocationSelect value={locationId} onChange={setLocationId} />
            </div>
            <div className="space-y-1.5">
              <Label>Notice period</Label>
              <Select value={noticeId} onValueChange={setNoticeId}>
                <SelectTrigger><SelectValue placeholder="Select notice period" /></SelectTrigger>
                <SelectContent>
                  {(notices.data ?? []).map((n) => (
                    <SelectItem key={n.np_id} value={String(n.np_id)}>{n.np_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:col-span-2">
              <div className="space-y-1.5">
                <Label>Exp min</Label>
                <Input type="number" step="0.5" value={form.exp_min} onChange={(e) => set("exp_min", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Exp max</Label>
                <Input type="number" step="0.5" value={form.exp_max} onChange={(e) => set("exp_max", e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Relevant exp</Label>
                <Input type="number" step="0.5" value={form.relevant_exp} onChange={(e) => set("relevant_exp", e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Current CTC (LPA)</Label>
              <Input type="number" step="0.5" value={form.current_ctc_lpa} onChange={(e) => set("current_ctc_lpa", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Expected CTC (LPA)</Label>
              <Input type="number" step="0.5" value={form.expected_ctc_lpa} onChange={(e) => set("expected_ctc_lpa", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Work mode</Label>
              <Select value={workModeId} onValueChange={setWorkModeId}>
                <SelectTrigger><SelectValue placeholder="Select work mode" /></SelectTrigger>
                <SelectContent>
                  {(workModes.data ?? []).map((w) => (
                    <SelectItem key={w.work_mode_id} value={String(w.work_mode_id)}>{w.work_mode_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Source</Label>
              <Select value={sourceId} onValueChange={setSourceId}>
                <SelectTrigger><SelectValue placeholder="Select source" /></SelectTrigger>
                <SelectContent>
                  {(sources.data ?? []).map((s) => (
                    <SelectItem key={s.source_id} value={String(s.source_id)}>{s.source_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Education</Label>
              <Input value={form.highest_qualification} onChange={(e) => set("highest_qualification", e.target.value)} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Skills</Label>
              <SkillMultiSelect value={skillIds} onChange={setSkillIds} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Certifications</Label>
              <Textarea rows={2} value={form.certifications} onChange={(e) => set("certifications", e.target.value)} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Additional notes</Label>
              <Textarea rows={2} value={form.additional_notes} onChange={(e) => set("additional_notes", e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <Checkbox checked={form.is_willing_to_relocate} onCheckedChange={(v) => set("is_willing_to_relocate", !!v)} />
              Willing to relocate
            </label>
            <label className="flex items-center gap-2 rounded-md border bg-accent/30 px-3 py-2 text-sm sm:col-span-2">
              <Checkbox checked={verified} onCheckedChange={(v) => setVerified(!!v)} />
              Mark profile as <span className="font-medium">verified</span> (records you + timestamp — typically after a screening call)
            </label>
          </div>
        </DialogBody>

        <DialogFooter className="flex-wrap gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="ghost" onClick={() => submit()} disabled={verify.isPending}>
            {verify.isPending ? "Saving…" : "Save profile only"}
          </Button>
          {/* One decision, made right here (replaces the separate Review step). */}
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => submit("SHORTLIST")} disabled={verify.isPending || !requirementId}
                    title={requirementId ? "" : "Open from a requirement to shortlist"}>
              Shortlist
            </Button>
            <Button variant="outline" onClick={() => submit("NOT_SUITABLE")} disabled={verify.isPending || !requirementId}>
              Not Suitable
            </Button>
            <Button variant="outline" onClick={() => submit("SAVE")} disabled={verify.isPending}>
              Save to Talent Pool
            </Button>
            <Button variant="outline" className="text-destructive" onClick={() => submit("FAKE")} disabled={verify.isPending}>
              Fake
            </Button>
            <Button variant="outline" className="text-destructive" onClick={() => submit("BLACKLIST")} disabled={verify.isPending}>
              Blacklist
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
