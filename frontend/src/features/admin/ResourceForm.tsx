import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AlertTriangle, Lock, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { CountrySelect } from "@/components/form/CountrySelect";
import { StateSelect } from "@/components/form/StateSelect";
import { DomainSelect } from "@/components/form/DomainSelect";
import { ResourceSelectField } from "./ResourceSelectField";
import { useMasterForm } from "./useMasterForm";
import type { ResourceConfig } from "./config";
import type { ResourceRow } from "./api";

export function ResourceForm({
  open,
  onClose,
  config,
  initial,
  rows,
  onCreate,
  onUpdate,
  onReactivate,
  saving,
}: {
  open: boolean;
  onClose: () => void;
  config: ResourceConfig;
  initial: ResourceRow | null;
  rows: ResourceRow[];
  onCreate: (values: ResourceRow) => void;
  onUpdate: (values: ResourceRow) => void;
  onReactivate: (row: ResourceRow) => void;
  saving: boolean;
}) {
  const hasTextarea = config.fields.some((f) => f.type === "textarea");
  const {
    isEdit,
    values,
    touched,
    setField,
    editCode,
    blurField,
    setAllTouched,
    fieldErrors,
    duplicate,
    activeDup,
    inactiveDup,
    similar,
    hasErrors,
    buildPayload,
    labelFor,
  } = useMasterForm({ config, rows, open, initial });

  const canSave = !saving && !hasErrors && !activeDup && !inactiveDup;

  function submit() {
    setAllTouched();
    if (!canSave) return;
    const payload = buildPayload();
    if (isEdit) onUpdate(payload);
    else onCreate(payload);
  }

  const dupLabels = duplicate ? duplicate.group.map(labelFor).join(", ").toLowerCase() : "";
  const autoCode = config.autoCode;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={hasTextarea ? "max-w-2xl" : "max-w-md"}>
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit ${config.singular}` : `New ${config.singular}`}</DialogTitle>
          <DialogDescription>
            {isEdit ? "Update this record." : `Add a new ${config.singular} to the master list.`}
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-3">
          {config.fields.map((f) => {
            const err = touched[f.name] ? fieldErrors[f.name] : undefined;
            const isAutoCode = f.name === autoCode?.field;
            return (
              <div key={f.name} className="space-y-1.5">
                <Label className="flex items-center gap-1.5">
                  {f.label}
                  {f.required && (!isAutoCode || !isEdit) && <span className="text-destructive"> *</span>}
                  {isAutoCode && isEdit && <Lock className="h-3 w-3 text-muted-foreground" />}
                </Label>
                {isAutoCode && isEdit ? (
                  // Frozen after creation — permanent system identifier.
                  <>
                    <Input
                      value={values[f.name] ?? ""}
                      readOnly
                      tabIndex={-1}
                      aria-readonly
                      className="cursor-not-allowed bg-muted font-mono text-xs text-muted-foreground"
                    />
                    <p className="text-xs text-muted-foreground">
                      Permanent system identifier — can't be changed after creation.
                    </p>
                  </>
                ) : isAutoCode ? (
                  // Create mode: auto-filled from the name, editable once for a
                  // shorter code; stops auto-updating after the first manual edit.
                  <>
                    <Input
                      value={values[f.name] ?? ""}
                      onChange={(e) => editCode(e.target.value)}
                      onBlur={() => blurField(f)}
                      placeholder="Generated from the name"
                      className={cn("font-mono text-xs uppercase", err && "border-destructive focus-visible:ring-destructive")}
                      aria-invalid={!!err}
                    />
                    {err ? (
                      <p className="text-xs text-destructive">{err}</p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Auto-filled from the name — you can edit it now for a shorter code, but it's locked after creation.
                      </p>
                    )}
                  </>
                ) : f.type === "select" ? (
                  <ResourceSelectField field={f} value={values[f.name]} onChange={(v) => setField(f.name, v)} />
                ) : f.type === "country" ? (
                  <CountrySelect value={values[f.name] ?? ""} onChange={(v) => setField(f.name, v)} />
                ) : f.type === "state" ? (
                  <StateSelect value={values[f.name] ?? ""} onChange={(v) => setField(f.name, v)} invalid={!!err} />
                ) : f.type === "domain" ? (
                  <DomainSelect
                    value={values[f.name] === "" || values[f.name] == null ? null : Number(values[f.name])}
                    onChange={(v) => setField(f.name, v)}
                    invalid={!!err}
                  />
                ) : f.type === "textarea" ? (
                  <Textarea
                    rows={f.rows ?? 4}
                    value={values[f.name] ?? ""}
                    onChange={(e) => setField(f.name, e.target.value)}
                    onBlur={() => blurField(f)}
                    placeholder={f.placeholder}
                    className="font-mono text-xs leading-relaxed"
                  />
                ) : (
                  <Input
                    type={f.type === "number" ? "number" : f.type === "password" ? "password" : "text"}
                    value={values[f.name] ?? ""}
                    onChange={(e) => setField(f.name, e.target.value)}
                    onBlur={() => blurField(f)}
                    placeholder={f.type === "password" && isEdit ? "Leave blank to keep current" : f.placeholder}
                    autoComplete={f.type === "password" ? "new-password" : undefined}
                    className={cn(err && "border-destructive focus-visible:ring-destructive")}
                    aria-invalid={!!err}
                  />
                )}
                {/* The auto-code branches render their own error/helper text. */}
                {!isAutoCode && err && <p className="text-xs text-destructive">{err}</p>}
                {!isAutoCode && f.hint && !err && <p className="text-xs text-muted-foreground">{f.hint}</p>}
              </div>
            );
          })}

          {/* Active duplicate — blocks save */}
          {activeDup && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              A {config.singular.toLowerCase()} with this {dupLabels} already exists.
            </p>
          )}

          {/* Inactive duplicate — offer reactivation instead of a new row */}
          {inactiveDup && (
            <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <div className="space-y-1.5">
                <p>
                  An <span className="font-medium">inactive</span> {config.singular.toLowerCase()} with this {dupLabels}{" "}
                  already exists. Reactivate it instead of creating a duplicate.
                </p>
                <Button size="sm" variant="outline" onClick={() => onReactivate(inactiveDup.match)}>
                  <RotateCcw className="h-3.5 w-3.5" /> Reactivate it
                </Button>
              </div>
            </div>
          )}

          {/* Similar (fuzzy) — non-blocking warning */}
          {!duplicate && similar.length > 0 && (
            <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              Similar to {similar.map((s) => `"${s[config.similarField!]}"`).join(", ")} — make sure this isn't a duplicate.
            </p>
          )}

          <div className="flex items-center gap-2 pt-1">
            <Checkbox id="active" checked={!!values.is_active} onCheckedChange={(c) => setField("is_active", !!c)} />
            <Label htmlFor="active" className="font-normal">
              Active
            </Label>
          </div>
        </DialogBody>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSave}>
            {saving ? "Saving…" : isEdit ? "Save changes" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
