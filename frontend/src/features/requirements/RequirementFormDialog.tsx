import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
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
import { Textarea } from "@/components/ui/textarea";
import { FormSelect } from "@/components/form/FormSelect";
import { SkillMultiSelect } from "@/components/form/SkillMultiSelect";
import { LocationSelect } from "@/components/form/LocationSelect";
import { useCreateRequirement, useUpdateRequirement } from "./api";
import type { Requirement } from "./types";
import {
  useClients,
  useClientManagers,
  useNoticePeriods,
  usePriorities,
  useReqTypes,
} from "@/lib/lookups";

const schema = z
  .object({
    client: z.string().min(1, "Client is required"),
    client_mgr: z.string().optional(),
    client_req_id: z.string().optional(),
    req_type: z.string().min(1, "Type is required"),
    jd_role_name: z.string().min(1, "Role name is required"),
    exp_min: z.string().optional(),
    exp_max: z.string().optional(),
    jd_rate_lpa: z.string().optional(),
    np: z.string().optional(),
    priority: z.string().optional(),
    positions_open: z.string().min(1, "Required"),
    // "Required by" is the user's business deadline → target_fill_date (Target
    // Close). It is NOT the creation date (that's system-generated `created_on`).
    target_fill_date: z.string().min(1, "Required by date is required"),
    jd_text: z.string().optional(),
  })
  .refine((d) => !d.exp_min || !d.exp_max || Number(d.exp_max) >= Number(d.exp_min), {
    message: "Max must be ≥ min",
    path: ["exp_max"],
  });

type FormValues = z.infer<typeof schema>;

function num(v?: string) {
  return v && v !== "" ? Number(v) : undefined;
}

export function RequirementFormDialog({
  open,
  onOpenChange,
  requirement,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  requirement?: Requirement | null;
}) {
  const isEdit = !!requirement;
  const { register, handleSubmit, control, reset, watch, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { positions_open: "1", target_fill_date: "" },
  });

  const clients = useClients();
  const clientManagers = useClientManagers();
  const reqTypes = useReqTypes();
  const notices = useNoticePeriods();
  const priorities = usePriorities();
  const createReq = useCreateRequirement();
  const updateReq = useUpdateRequirement();

  // Skills are a 3-slot schema (skill1/2/3) → multi-select capped at 3.
  const [skillIds, setSkillIds] = useState<number[]>([]);
  // Location is a single FK; kept in local state so the searchable LocationSelect
  // (with inline "+ add") can drive it without a RHF field.
  const [locationId, setLocationId] = useState<number | null>(null);
  useEffect(() => {
    if (!open) return;
    if (requirement) {
      reset({
        client: requirement.client != null ? String(requirement.client) : "",
        client_mgr: requirement.client_mgr != null ? String(requirement.client_mgr) : "",
        client_req_id: requirement.client_req_id ?? "",
        req_type: requirement.req_type != null ? String(requirement.req_type) : "",
        jd_role_name: requirement.jd_role_name,
        exp_min: requirement.exp_min ?? "",
        exp_max: requirement.exp_max ?? "",
        jd_rate_lpa: requirement.jd_rate_lpa ?? "",
        np: requirement.np != null ? String(requirement.np) : "",
        priority: requirement.priority != null ? String(requirement.priority) : "",
        positions_open: String(requirement.positions_open),
        target_fill_date: requirement.target_fill_date ?? "",
        jd_text: requirement.jd_text ?? "",
      });
      setSkillIds([requirement.skill1, requirement.skill2, requirement.skill3].filter((x): x is number => x != null));
      setLocationId(requirement.location ?? null);
    } else {
      reset({ positions_open: "1", target_fill_date: "" });
      setSkillIds([]);
      setLocationId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, requirement]);

  const selectedClient = watch("client");

  const opt = {
    clients: (clients.data ?? []).map((c) => ({ value: String(c.client_id), label: c.client_name })),
    managers: (clientManagers.data ?? [])
      .filter((m) => String(m.client) === selectedClient)
      .map((m) => ({ value: String(m.client_mgr_id), label: m.manager_name })),
    reqTypes: (reqTypes.data ?? []).map((r) => ({ value: String(r.req_type_id), label: r.req_type_name })),
    notices: (notices.data ?? []).map((n) => ({ value: String(n.np_id), label: n.np_name })),
    priorities: (priorities.data ?? []).map((p) => ({ value: String(p.priority_id), label: p.priority_name })),
  };

  async function onSubmit(v: FormValues) {
    const payload: Record<string, unknown> = {
      client: Number(v.client),
      client_mgr: num(v.client_mgr) ?? null,
      client_req_id: v.client_req_id || null,
      req_type: Number(v.req_type),
      jd_role_name: v.jd_role_name,
      location: locationId ?? null,
      exp_min: num(v.exp_min) ?? null,
      exp_max: num(v.exp_max) ?? null,
      jd_rate_lpa: num(v.jd_rate_lpa) ?? null,
      np: num(v.np) ?? null,
      priority: num(v.priority) ?? null,
      skill1: skillIds[0] ?? null,
      skill2: skillIds[1] ?? null,
      skill3: skillIds[2] ?? null,
      target_fill_date: v.target_fill_date,
      jd_text: v.jd_text || null,
    };
    try {
      if (isEdit && requirement) {
        // positions_open is deliberately NOT sent — seats are managed via the
        // positions panel, so editing here never disturbs them.
        await updateReq.mutateAsync({ reqId: requirement.req_id, payload });
        toast.success(`Requirement ${requirement.req_tracker_no} updated`);
      } else {
        payload.positions_open = Number(v.positions_open);
        const created = await createReq.mutateAsync(payload);
        toast.success(`Requirement ${created.req_tracker_no} created`);
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(
        apiErrorMessage(
          err,
          isEdit ? "Could not update the requirement. Please check the fields."
                 : "Could not create the requirement. Please check the fields.",
        ),
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit requirement" : "New requirement"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this requisition's details. Status and positions are managed separately."
              : "Create a job requisition. A tracker number is generated automatically."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col">
          <DialogBody>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormSelect control={control} name="client" label="Client" placeholder="Select client" options={opt.clients} errors={errors} required />
            <FormSelect
              control={control}
              name="client_mgr"
              label="Client manager"
              placeholder={selectedClient ? "Select manager" : "Select a client first"}
              options={opt.managers}
              errors={errors}
              disabled={!selectedClient}
            />
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Role name <span className="text-destructive">*</span></Label>
              <Input {...register("jd_role_name")} placeholder="e.g. Senior Python Developer" />
              {errors.jd_role_name && <p className="text-xs text-destructive">{errors.jd_role_name.message}</p>}
            </div>
            <FormSelect control={control} name="req_type" label="Type" placeholder="FTE / TPR" options={opt.reqTypes} errors={errors} required />
            <div className="space-y-1.5">
              <Label>Client Req ID</Label>
              <Input {...register("client_req_id")} placeholder="Client's own reference" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="req-location">Location</Label>
              <LocationSelect id="req-location" value={locationId} onChange={setLocationId} />
            </div>
            <FormSelect control={control} name="np" label="Notice period" placeholder="Select notice period" options={opt.notices} errors={errors} />
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Exp min (yrs)</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_min")} />
              </div>
              <div className="space-y-1.5">
                <Label>Exp max (yrs)</Label>
                <Input type="number" step="0.5" min="0" {...register("exp_max")} />
                {errors.exp_max && <p className="text-xs text-destructive">{errors.exp_max.message}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Rate (LPA)</Label>
                <Input type="number" step="0.5" min="0" {...register("jd_rate_lpa")} />
              </div>
              <div className="space-y-1.5">
                <Label>Positions <span className="text-destructive">*</span></Label>
                <Input type="number" min="1" {...register("positions_open")} disabled={isEdit} />
                {isEdit ? (
                  <p className="text-xs text-muted-foreground">Managed via positions.</p>
                ) : (
                  errors.positions_open && <p className="text-xs text-destructive">{errors.positions_open.message}</p>
                )}
              </div>
            </div>
            <FormSelect control={control} name="priority" label="Priority" placeholder="Select priority" options={opt.priorities} errors={errors} />
            <div className="space-y-1.5">
              <Label>Required by <span className="text-destructive">*</span></Label>
              <Input type="date" {...register("target_fill_date")} />
              {errors.target_fill_date && <p className="text-xs text-destructive">{errors.target_fill_date.message}</p>}
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Skills</Label>
              <SkillMultiSelect value={skillIds} onChange={setSkillIds} max={3} placeholder="Select up to 3 skills" />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Job description</Label>
              <Textarea rows={4} {...register("jd_text")} placeholder="Paste the JD / key responsibilities…" />
            </div>
            </div>
          </DialogBody>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isEdit
                ? isSubmitting ? "Saving…" : "Save changes"
                : isSubmitting ? "Creating…" : "Create requirement"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
