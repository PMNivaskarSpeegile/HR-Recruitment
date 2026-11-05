import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { isAxiosError } from "axios";
import { apiErrorMessage } from "@/lib/apiError";
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
import { Checkbox } from "@/components/ui/checkbox";
import { FormSelect } from "@/components/form/FormSelect";
import { SkillMultiSelect } from "@/components/form/SkillMultiSelect";
import { useLocations, useNoticePeriods, useSources, useWorkModes } from "@/lib/lookups";
import { RequirementSelect } from "@/features/requirements/RequirementSelect";
import { useCreateCandidate, useTagRequirement, useVerifyCandidateProfile } from "./api";
import { DuplicateDetectedDialog, type DuplicateInfo } from "./DuplicateDetectedDialog";
import type { Candidate } from "./types";

const schema = z
  .object({
    candidate_name: z.string().min(1, "Name is required"),
    mobile: z.string().min(7, "Enter a valid mobile number"),
    email: z.string().email("Enter a valid email"),
    current_company: z.string().optional(),
    exp_min: z.string().optional(),
    exp_max: z.string().optional(),
    current_location: z.string().optional(),
    notice_period: z.string().optional(),
    work_mode: z.string().optional(),
    source: z.string().optional(),
    current_ctc_lpa: z.string().optional(),
    expected_ctc_lpa: z.string().optional(),
    highest_qualification: z.string().optional(),
    is_willing_to_relocate: z.boolean().optional(),
    requirement: z.string().optional(),
  })
  .refine((d) => !d.exp_min || !d.exp_max || Number(d.exp_max) >= Number(d.exp_min), {
    message: "Max must be ≥ min",
    path: ["exp_max"],
  });

type FormValues = z.infer<typeof schema>;

function num(v?: string) {
  return v && v !== "" ? Number(v) : undefined;
}

export function CandidateFormDialog({
  open,
  onOpenChange,
  candidate = null,
  readOnly = false,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  // When set, the dialog edits (or, with readOnly, just displays) this
  // existing candidate instead of creating a new one — same form,
  // pre-populated with the candidate's current data.
  candidate?: Candidate | null;
  // View-only: every field is disabled and there's no Save button. Used when
  // opened from the Candidate Details panel just to display the record.
  readOnly?: boolean;
}) {
  const isEdit = candidate != null;
  const isViewOnly = isEdit && readOnly;
  const { register, handleSubmit, control, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { is_willing_to_relocate: false },
  });

  const locations = useLocations();
  const notices = useNoticePeriods();
  const workModes = useWorkModes();
  const sources = useSources();
  const createCandidate = useCreateCandidate();
  const updateCandidate = useVerifyCandidateProfile();
  // Reused as-is for the edit flow too: the same pk-scoped action the
  // Candidate Details "Tag to requirement" dialog and the create flow's
  // `requirement` field both drive — puts the candidate in that requirement's
  // Review Pool. Never inherits the requirement's skills (see backend).
  const tagRequirement = useTagRequirement();
  const isSaving = isEdit ? updateCandidate.isPending || tagRequirement.isPending : isSubmitting;

  const [skillIds, setSkillIds] = useState<number[]>([]);
  const [dupInfo, setDupInfo] = useState<DuplicateInfo | null>(null);

  // Pre-populate from the candidate being edited; reset to a blank form when
  // adding a new one. Re-runs whenever the dialog (re)opens.
  useEffect(() => {
    if (!open) return;
    if (candidate) {
      reset({
        candidate_name: candidate.candidate_name ?? "",
        mobile: candidate.mobile ?? "",
        email: candidate.email ?? "",
        current_company: candidate.current_company ?? "",
        exp_min: candidate.exp_min != null ? String(candidate.exp_min) : "",
        exp_max: candidate.exp_max != null ? String(candidate.exp_max) : "",
        current_location: candidate.current_location != null ? String(candidate.current_location) : "",
        notice_period: candidate.notice_period != null ? String(candidate.notice_period) : "",
        work_mode: candidate.work_mode != null ? String(candidate.work_mode) : "",
        source: candidate.source != null ? String(candidate.source) : "",
        current_ctc_lpa: candidate.current_ctc_lpa != null ? String(candidate.current_ctc_lpa) : "",
        expected_ctc_lpa: candidate.expected_ctc_lpa != null ? String(candidate.expected_ctc_lpa) : "",
        highest_qualification: candidate.highest_qualification ?? "",
        is_willing_to_relocate: !!candidate.is_willing_to_relocate,
        requirement: "",
      });
      // Synchronizing local state with react-hook-form's reset() above, run
      // once per dialog-open for a specific candidate — the standard pattern
      // for re-populating an uncontrolled form, not a derivable render value.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSkillIds(candidate.skill_ids ?? []);
    } else {
      reset({ is_willing_to_relocate: false });
      setSkillIds([]);
    }
  }, [open, candidate, reset]);

  const opt = {
    locations: (locations.data ?? []).map((l) => ({ value: String(l.location_id), label: `${l.city}, ${l.state}` })),
    notices: (notices.data ?? []).map((n) => ({ value: String(n.np_id), label: n.np_name })),
    workModes: (workModes.data ?? []).map((w) => ({ value: String(w.work_mode_id), label: w.work_mode_name })),
    sources: (sources.data ?? []).map((s) => ({ value: String(s.source_id), label: s.source_name })),
  };

  async function onSubmit(v: FormValues) {
    if (isViewOnly) return; // no Save button is rendered, but guard defensively
    if (isEdit && candidate) {
      // Edit an existing candidate — updates the SAME record (matched by id,
      // not by mobile), via the existing Verify & Update profile endpoint so a
      // mobile/email change is safely re-checked against duplicates rather than
      // risking a second candidate being created. This is a plain edit, not a
      // screening "verification", so it never stamps profile_verified.
      const payload: Record<string, unknown> = {
        candidate_name: v.candidate_name,
        mobile: v.mobile,
        email: v.email,
        current_company: v.current_company || null,
        exp_min: num(v.exp_min) ?? null,
        exp_max: num(v.exp_max) ?? null,
        current_location: num(v.current_location) ?? null,
        notice_period: num(v.notice_period) ?? null,
        work_mode: num(v.work_mode) ?? null,
        source: num(v.source) ?? null,
        current_ctc_lpa: num(v.current_ctc_lpa) ?? null,
        expected_ctc_lpa: num(v.expected_ctc_lpa) ?? null,
        highest_qualification: v.highest_qualification || null,
        is_willing_to_relocate: !!v.is_willing_to_relocate,
        skill_ids: skillIds,
        verified: false,
      };
      try {
        const res = await updateCandidate.mutateAsync({ id: candidate.cv_id, ...payload });
        // Tag to requirement is a separate action (adds to that requirement's
        // Review Pool via the same endpoint the Candidate Details panel uses) —
        // it isn't part of the profile itself, so it runs as its own step after
        // the profile save succeeds, same as the create flow does internally.
        if (v.requirement) {
          try {
            await tagRequirement.mutateAsync({ id: candidate.cv_id, requirementIds: [Number(v.requirement)] });
          } catch (tagErr) {
            toast.error(apiErrorMessage(tagErr, "Candidate updated, but could not tag to that requirement."));
            onOpenChange(false);
            return;
          }
        }
        toast.success(`Candidate ${res.candidate.cv_serial} updated`);
        onOpenChange(false);
      } catch (err) {
        const fallback = isAxiosError(err) && err.response?.status === 409
          ? "That mobile/email already belongs to another candidate."
          : "Could not save the candidate. Please check the fields.";
        toast.error(apiErrorMessage(err, fallback));
      }
      return;
    }

    const payload: Record<string, unknown> = {
      candidate_name: v.candidate_name,
      mobile: v.mobile,
      email: v.email,
      current_company: v.current_company || undefined,
      exp_min: num(v.exp_min),
      exp_max: num(v.exp_max),
      current_location: num(v.current_location),
      notice_period: num(v.notice_period),
      work_mode: num(v.work_mode),
      source: num(v.source),
      current_ctc_lpa: num(v.current_ctc_lpa),
      expected_ctc_lpa: num(v.expected_ctc_lpa),
      highest_qualification: v.highest_qualification || undefined,
      is_willing_to_relocate: !!v.is_willing_to_relocate,
      requirement: num(v.requirement),
      skill_ids: skillIds,
    };
    try {
      const res = await createCandidate.mutateAsync(payload);
      if (res.action === "UPDATED") toast.success(`Existing candidate ${res.candidate.cv_serial} updated`);
      else toast.success(`Candidate ${res.candidate.cv_serial} added`);
      reset({ is_willing_to_relocate: false });
      setSkillIds([]);
      onOpenChange(false);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409 && err.response.data?.existing_candidate) {
        // Possible duplicate → open the read-only side-by-side review dialog.
        const d = err.response.data;
        setDupInfo({ reason: d.reason, existing_candidate: d.existing_candidate, submitted: d.submitted });
      } else {
        toast.error(apiErrorMessage(err, "Could not save the candidate. Please check the fields."));
      }
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isViewOnly ? "Candidate details" : isEdit ? "Edit candidate" : "Add candidate"}</DialogTitle>
          <DialogDescription>
            {isViewOnly
              ? "Read-only view of this candidate's profile. Use Edit from the candidate list to make changes."
              : isEdit
              ? "Update this candidate's details. Changes apply to their single master profile."
              : "Mobile number is the unique identifier. Duplicates are detected automatically."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <DialogBody>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Full name <span className="text-destructive">*</span></Label>
              <Input {...register("candidate_name")} placeholder="e.g. Arjun Sharma" disabled={isViewOnly} />
              {errors.candidate_name && <p className="text-xs text-destructive">{errors.candidate_name.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Mobile <span className="text-destructive">*</span></Label>
              <Input {...register("mobile")} placeholder="10-digit mobile" disabled={isViewOnly} />
              {errors.mobile && <p className="text-xs text-destructive">{errors.mobile.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Email <span className="text-destructive">*</span></Label>
              <Input type="email" {...register("email")} placeholder="name@example.com" disabled={isViewOnly} />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Current company</Label>
              <Input {...register("current_company")} disabled={isViewOnly} />
            </div>
            <FormSelect control={control} name="current_location" label="Current location" placeholder="Select location" options={opt.locations} errors={errors} disabled={isViewOnly} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Exp min</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_min")} disabled={isViewOnly} />
              </div>
              <div className="space-y-1.5">
                <Label>Exp max</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_max")} disabled={isViewOnly} />
                {errors.exp_max && <p className="text-xs text-destructive">{errors.exp_max.message}</p>}
              </div>
            </div>
            <FormSelect control={control} name="notice_period" label="Notice period" placeholder="Select notice period" options={opt.notices} errors={errors} disabled={isViewOnly} />
            <FormSelect control={control} name="work_mode" label="Work mode" placeholder="Select work mode" options={opt.workModes} errors={errors} disabled={isViewOnly} />
            <FormSelect control={control} name="source" label="Source" placeholder="Select source" options={opt.sources} errors={errors} disabled={isViewOnly} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Current CTC (LPA)</Label>
                <Input type="number" step="0.5" min="0" {...register("current_ctc_lpa")} disabled={isViewOnly} />
              </div>
              <div className="space-y-1.5">
                <Label>Expected CTC</Label>
                <Input type="number" step="0.5" min="0" {...register("expected_ctc_lpa")} disabled={isViewOnly} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Highest qualification</Label>
              <Input {...register("highest_qualification")} placeholder="e.g. B.Tech (CS)" disabled={isViewOnly} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Skills</Label>
              {isViewOnly ? (
                <div className="flex flex-wrap gap-1.5">
                  {candidate && candidate.skill_names && candidate.skill_names.length > 0 ? (
                    candidate.skill_names.map((name) => (
                      <span key={name} className="rounded bg-secondary px-2 py-0.5 text-xs">{name}</span>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">No skills recorded</span>
                  )}
                </div>
              ) : (
                <SkillMultiSelect value={skillIds} onChange={setSkillIds} placeholder="Search and add skills" />
              )}
            </div>
            {!isViewOnly && (
              <div className="space-y-1.5">
                <Label>Tag to requirement (optional)</Label>
                <Controller
                  control={control}
                  name="requirement"
                  render={({ field }) => (
                    <RequirementSelect
                      value={field.value ?? ""}
                      onChange={(id) => field.onChange(id)}
                      clearable
                      clearLabel="None"
                      placeholder="Adds this candidate to the requirement's Review Pool"
                    />
                  )}
                />
              </div>
            )}
            <div className="flex items-center gap-2 sm:col-span-2">
              <Controller
                control={control}
                name="is_willing_to_relocate"
                render={({ field }) => (
                  <Checkbox
                    id="relocate"
                    checked={!!field.value}
                    onCheckedChange={field.onChange}
                    disabled={isViewOnly}
                  />
                )}
              />
              <Label htmlFor="relocate" className="font-normal text-muted-foreground">
                Willing to relocate
              </Label>
            </div>
            </div>
          </DialogBody>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {isViewOnly ? "Close" : "Cancel"}
            </Button>
            {!isViewOnly && (
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Saving…" : isEdit ? "Save changes" : "Add candidate"}
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <DuplicateDetectedDialog
      info={dupInfo}
      onCancel={() => setDupInfo(null)}
      onSubmitted={() => {
        setDupInfo(null);
        reset({ is_willing_to_relocate: false });
        setSkillIds([]);
        onOpenChange(false);
      }}
    />
    </>
  );
}