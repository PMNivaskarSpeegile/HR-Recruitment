import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
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
import { useCreateCandidate } from "./api";
import { DuplicateDetectedDialog, type DuplicateInfo } from "./DuplicateDetectedDialog";

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

export function CandidateFormDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { register, handleSubmit, control, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { is_willing_to_relocate: false },
  });

  const locations = useLocations();
  const notices = useNoticePeriods();
  const workModes = useWorkModes();
  const sources = useSources();
  const createCandidate = useCreateCandidate();

  const [skillIds, setSkillIds] = useState<number[]>([]);
  const [dupInfo, setDupInfo] = useState<DuplicateInfo | null>(null);
  useEffect(() => {
    if (open) setSkillIds([]);
  }, [open]);

  const opt = {
    locations: (locations.data ?? []).map((l) => ({ value: String(l.location_id), label: `${l.city}, ${l.state}` })),
    notices: (notices.data ?? []).map((n) => ({ value: String(n.np_id), label: n.np_name })),
    workModes: (workModes.data ?? []).map((w) => ({ value: String(w.work_mode_id), label: w.work_mode_name })),
    sources: (sources.data ?? []).map((s) => ({ value: String(s.source_id), label: s.source_name })),
  };

  async function onSubmit(v: FormValues) {
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
    } catch (err: any) {
      if (err?.response?.status === 409 && err.response.data?.existing_candidate) {
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
          <DialogTitle>Add candidate</DialogTitle>
          <DialogDescription>Mobile number is the unique identifier. Duplicates are detected automatically.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <DialogBody>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Full name <span className="text-destructive">*</span></Label>
              <Input {...register("candidate_name")} placeholder="e.g. Arjun Sharma" />
              {errors.candidate_name && <p className="text-xs text-destructive">{errors.candidate_name.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Mobile <span className="text-destructive">*</span></Label>
              <Input {...register("mobile")} placeholder="10-digit mobile" />
              {errors.mobile && <p className="text-xs text-destructive">{errors.mobile.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Email <span className="text-destructive">*</span></Label>
              <Input type="email" {...register("email")} placeholder="name@example.com" />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Current company</Label>
              <Input {...register("current_company")} />
            </div>
            <FormSelect control={control} name="current_location" label="Current location" placeholder="Select location" options={opt.locations} errors={errors} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Exp min</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_min")} />
              </div>
              <div className="space-y-1.5">
                <Label>Exp max</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_max")} />
                {errors.exp_max && <p className="text-xs text-destructive">{errors.exp_max.message}</p>}
              </div>
            </div>
            <FormSelect control={control} name="notice_period" label="Notice period" placeholder="Select notice period" options={opt.notices} errors={errors} />
            <FormSelect control={control} name="work_mode" label="Work mode" placeholder="Select work mode" options={opt.workModes} errors={errors} />
            <FormSelect control={control} name="source" label="Source" placeholder="Select source" options={opt.sources} errors={errors} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Current CTC (LPA)</Label>
                <Input type="number" step="0.5" min="0" {...register("current_ctc_lpa")} />
              </div>
              <div className="space-y-1.5">
                <Label>Expected CTC</Label>
                <Input type="number" step="0.5" min="0" {...register("expected_ctc_lpa")} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Highest qualification</Label>
              <Input {...register("highest_qualification")} placeholder="e.g. B.Tech (CS)" />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Skills</Label>
              <SkillMultiSelect value={skillIds} onChange={setSkillIds} placeholder="Search and add skills" />
            </div>
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
                    placeholder="Also inherit the requirement's skills"
                  />
                )}
              />
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <Controller
                control={control}
                name="is_willing_to_relocate"
                render={({ field }) => (
                  <Checkbox id="relocate" checked={!!field.value} onCheckedChange={field.onChange} />
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
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Add candidate"}
            </Button>
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
