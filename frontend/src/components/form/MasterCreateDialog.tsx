import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api } from "@/api/client";
import { CountrySelect } from "@/components/form/CountrySelect";
import { StateSelect } from "@/components/form/StateSelect";
import { DomainSelect } from "@/components/form/DomainSelect";
import { RESOURCES } from "@/features/admin/config";
import { useResourceList } from "@/features/admin/api";
import type { ResourceRow } from "@/features/admin/api";
import { useMasterForm } from "@/features/admin/useMasterForm";

/**
 * Inline create-only master dialog used from workflow forms (e.g. adding a
 * missing Skill / Location while creating a Requirement). It reuses the SAME
 * config entry, validation, normalisation and duplicate detection as the Admin
 * Master Data screen (via `useMasterForm`) — there is no separate validation
 * logic — but is strictly create-only: no edit, delete, activate/deactivate or
 * reactivate. New records are always Active. On success the created row is
 * appended to the lookup cache (so it appears + can be selected immediately
 * without a refresh) and returned via `onCreated`.
 *
 * Permissions are enforced server-side (`CanManageReferenceData`): only Admins
 * and Hiring Managers can POST; the trigger that renders this dialog is itself
 * role-gated.
 */
export function MasterCreateDialog({
  open,
  onOpenChange,
  configKey,
  prefill,
  onCreated,
  aside,
  dropTargetField,
  allowMultiple = false,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  configKey: string;
  // Seed values for fields (e.g. the text the user had typed in the dropdown).
  prefill?: Record<string, unknown>;
  onCreated: (row: ResourceRow) => void;
  // Optional read-only reference panel shown beside the form (e.g. the list of
  // unmapped locations to add). Purely contextual — never a second form.
  aside?: ReactNode;
  // Optional: name of a text field that accepts a drag-and-drop text payload
  // (text/plain). Dropping REPLACES the field value (then it stays editable).
  // Used so an unmapped city can be dragged onto the City input.
  dropTargetField?: string;
  // Opt-in "save & add another": after creating, the dialog stays open and the
  // form resets, so several records can be added in one sitting. Default false
  // keeps the original create-then-close behaviour for existing callers.
  allowMultiple?: boolean;
}) {
  const config = RESOURCES.find((r) => r.key === configKey)!;
  const qc = useQueryClient();
  // All rows (incl. inactive) so we can warn on an inactive duplicate too, matching
  // the Master Data screen.
  const list = useResourceList(config.endpoint, false);
  const rows = list.data ?? [];

  const f = useMasterForm({ config, rows, open });
  const { values, touched, setField, blurField, setAllTouched, fieldErrors, duplicate, activeDup, inactiveDup, similar, hasErrors, buildPayload, labelFor, reset } = f;

  // Field currently under a drag (for the drop-target highlight).
  const [dragOverField, setDragOverField] = useState<string | null>(null);
  // "Save & add another": labels of records created during this open session.
  const [addedThisSession, setAddedThisSession] = useState<string[]>([]);
  useEffect(() => {
    if (open) setAddedThisSession([]);
  }, [open]);
  const rowLabel = (row: ResourceRow) => {
    const first = config.fields[0]?.name;
    return String((first && row[first]) ?? config.singular);
  };

  // Apply prefill once the form has been (re)initialised for this open.
  // useMasterForm resets on `open`; seed afterwards via setField.
  const seededRef = usePrefill(open, prefill, setField);

  const create = useMutation({
    mutationFn: async (body: ResourceRow) => (await api.post<ResourceRow>(config.endpoint, body)).data,
    onSuccess: (createdRow) => {
      // Append to the active-only lookup cache that dropdowns read from
      // (["master", <key>]) so the new option is instantly selectable, then
      // invalidate so every other consumer refetches.
      qc.setQueryData<ResourceRow[]>(["master", config.key], (old) => (old ? [...old, createdRow] : [createdRow]));
      qc.invalidateQueries({ queryKey: ["master"] });
      qc.invalidateQueries({ queryKey: ["resource", config.endpoint] });
    },
  });

  const dupLabels = duplicate ? duplicate.group.map(labelFor).join(", ").toLowerCase() : "";
  const canSave = !create.isPending && !hasErrors && !activeDup && !inactiveDup;

  async function save() {
    setAllTouched();
    if (!canSave) return;
    try {
      const createdRow = await create.mutateAsync(buildPayload());
      toast.success(`${config.singular[0].toUpperCase()}${config.singular.slice(1)} added`);
      onCreated(createdRow);
      if (allowMultiple) {
        // Keep the dialog open and clear the form so the admin can add the next
        // one without reopening. "Done" closes when they're finished.
        setAddedThisSession((s) => [...s, rowLabel(createdRow)]);
        reset();
      } else {
        onOpenChange(false);
      }
    } catch (err: any) {
      // Surface the server's message (it runs the very same validation/dedupe).
      const data = err?.response?.data;
      const fieldErr = data?.error && typeof data.error === "object" ? Object.values(data.error)[0] : null;
      const msg =
        data?.code === "inactive_duplicate"
          ? `An inactive ${config.singular.toLowerCase()} with these details already exists. Ask an administrator to reactivate it.`
          : (Array.isArray(fieldErr) ? fieldErr[0] : fieldErr) ?? data?.detail ?? `Could not create the ${config.singular.toLowerCase()}.`;
      toast.error(msg);
    }
  }

  void seededRef;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onOpenChange(false)}>
      <DialogContent className={cn("max-w-md", aside && "max-w-2xl")}>
        <DialogHeader>
          <DialogTitle>New {config.singular}</DialogTitle>
          <DialogDescription>Add a {config.singular} to the master so it's available everywhere.</DialogDescription>
        </DialogHeader>

        <DialogBody className={cn(aside && "grid gap-5 sm:grid-cols-[minmax(0,1fr)_220px]")}>
          <div className="space-y-3">
          {config.fields.map((field) => {
            const err = touched[field.name] ? fieldErrors[field.name] : undefined;
            return (
              <div key={field.name} className="space-y-1.5">
                <Label>
                  {field.label}
                  {field.required && <span className="text-destructive"> *</span>}
                </Label>
                {field.type === "country" ? (
                  <CountrySelect value={values[field.name] ?? ""} onChange={(v) => setField(field.name, v)} />
                ) : field.type === "state" ? (
                  <StateSelect value={values[field.name] ?? ""} onChange={(v) => setField(field.name, v)} invalid={!!err} />
                ) : field.type === "domain" ? (
                  <DomainSelect
                    value={values[field.name] === "" || values[field.name] == null ? null : Number(values[field.name])}
                    onChange={(v) => setField(field.name, v)}
                    invalid={!!err}
                  />
                ) : (
                  <Input
                    autoFocus={field === config.fields[0]}
                    type={field.type === "number" ? "number" : "text"}
                    value={values[field.name] ?? ""}
                    onChange={(e) => setField(field.name, e.target.value)}
                    onBlur={() => blurField(field)}
                    placeholder={field.placeholder}
                    className={cn(
                      err && "border-destructive focus-visible:ring-destructive",
                      dragOverField === field.name && "border-primary ring-2 ring-primary",
                    )}
                    aria-invalid={!!err}
                    {...(dropTargetField === field.name && {
                      // Accept a dragged unmapped city: REPLACE the value (kept
                      // editable), then focus so the admin can fix spelling.
                      onDragOver: (e: React.DragEvent) => {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = "copy";
                        setDragOverField(field.name);
                      },
                      onDragLeave: () => setDragOverField(null),
                      onDrop: (e: React.DragEvent) => {
                        e.preventDefault();
                        setDragOverField(null);
                        const text = e.dataTransfer.getData("text/plain").trim();
                        if (text) {
                          setField(field.name, text);
                          (e.currentTarget as HTMLInputElement).focus();
                        }
                      },
                    })}
                  />
                )}
                {err && <p className="text-xs text-destructive">{err}</p>}
                {field.hint && !err && <p className="text-xs text-muted-foreground">{field.hint}</p>}
              </div>
            );
          })}

          {activeDup && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              A {config.singular.toLowerCase()} with this {dupLabels} already exists.
            </p>
          )}

          {inactiveDup && (
            <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <p>
                An <span className="font-medium">inactive</span> {config.singular.toLowerCase()} with this {dupLabels} already
                exists. Ask an administrator to reactivate it instead of creating a duplicate.
              </p>
            </div>
          )}

          {!duplicate && similar.length > 0 && (
            <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              Similar to {similar.map((s) => `"${s[config.similarField!]}"`).join(", ")} — make sure this isn't a duplicate.
            </p>
          )}

          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Status</span>
            <Badge variant="success">Active</Badge>
          </div>
          </div>
          {aside && (
            <aside className="rounded-md border bg-muted/30 p-3 text-sm">{aside}</aside>
          )}
        </DialogBody>

        <DialogFooter className="items-center">
          {allowMultiple && addedThisSession.length > 0 && (
            <span className="mr-auto text-xs text-muted-foreground">
              Added {addedThisSession.length}: {addedThisSession.join(", ")}
            </span>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {allowMultiple ? "Done" : "Cancel"}
          </Button>
          <Button onClick={save} disabled={!canSave}>
            {create.isPending ? "Saving…" : `Create ${config.singular}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Seed prefill values once per open (after useMasterForm's reset effect runs).
function usePrefill(open: boolean, prefill: Record<string, unknown> | undefined, setField: (n: string, v: unknown) => void) {
  const done = useRef(false);
  useEffect(() => {
    if (!open) {
      done.current = false;
      return;
    }
    if (done.current || !prefill) return;
    // Defer so it runs after useMasterForm's open-reset effect.
    const id = setTimeout(() => {
      Object.entries(prefill).forEach(([k, v]) => setField(k, v));
      done.current = true;
    }, 0);
    return () => clearTimeout(id);
  }, [open, prefill, setField]);
  return done;
}
