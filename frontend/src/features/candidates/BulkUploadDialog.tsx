import { useEffect, useMemo, useState } from "react";
import { Download, FileSpreadsheet, CheckCircle2, XCircle, AlertTriangle, Copy } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiErrorMessage } from "@/lib/apiError";
import { RequirementSelect } from "@/features/requirements/RequirementSelect";
import { useSources } from "@/lib/lookups";
import { downloadCandidateTemplate, useBulkPreview, useBulkImport } from "./api";
import type { BulkPreview, BulkImportReport, BulkRow } from "./api";

const STATUS_META: Record<string, { label: string; variant: "success" | "danger" | "warning" | "muted" | "blue" }> = {
  VALID: { label: "Will import", variant: "success" },
  UPDATE: { label: "Update existing", variant: "blue" },
  DUPLICATE: { label: "Duplicate → review", variant: "warning" },
  INVALID: { label: "Invalid", variant: "danger" },
  CREATED: { label: "Created", variant: "success" },
  UPDATED: { label: "Updated", variant: "blue" },
  ERROR: { label: "Error", variant: "danger" },
};

function csvCell(v: string) {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadErrorReport(rows: BulkRow[]) {
  const header = ["Excel Row", "Name", "Mobile", "Email", "Status", "Errors", "Warnings"];
  const lines = [header.join(",")];
  for (const r of rows) {
    lines.push([
      r.excel_row, r.name, r.mobile, r.email,
      STATUS_META[r.status]?.label ?? r.status,
      r.errors.join(" | "), r.warnings.join(" | "),
    ].map((c) => csvCell(String(c))).join(","));
  }
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "bulk_upload_report.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function SummaryChips({ s }: { s: NonNullable<BulkPreview["summary"]> }) {
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <span className="rounded bg-muted px-2 py-1 text-muted-foreground" title="Data rows detected in the file (header and blank rows excluded)">Total {s.total}</span>
      <span className="rounded bg-success/10 px-2 py-1 text-success" title="New candidates that will be imported">Valid {s.valid}</span>
      {s.update > 0 && <span className="rounded bg-primary/10 px-2 py-1 text-primary" title="Existing candidates (same mobile & email) that will be updated">Update {s.update}</span>}
      {s.duplicate > 0 && <span className="rounded bg-warning/15 px-2 py-1 text-foreground" title="Rows with the same mobile but a different email — sent to review, not imported">Duplicates {s.duplicate}</span>}
      <span className="rounded bg-destructive/10 px-2 py-1 text-destructive" title="Rows blocked from import due to validation errors">Invalid {s.invalid}</span>
      {s.warnings > 0 && <span className="rounded bg-muted px-2 py-1 text-muted-foreground" title="Number of rows that have one or more warnings (the row is still importable)">Warnings {s.warnings}</span>}
    </div>
  );
}

function RowList({ rows }: { rows: BulkRow[] }) {
  if (rows.length === 0) return null;
  return (
    <ul className="max-h-56 space-y-1.5 overflow-y-auto rounded-md border p-2 text-xs">
      {rows.map((r) => {
        const meta = STATUS_META[r.status] ?? { label: r.status, variant: "muted" as const };
        return (
          <li key={r.excel_row} className="flex flex-col gap-0.5 border-b pb-1.5 last:border-0 last:pb-0">
            <div className="flex items-center gap-2">
              <span className="font-medium tabular-nums text-muted-foreground">Row {r.excel_row}</span>
              <span className="font-medium">{r.name || "—"}</span>
              <span className="text-muted-foreground">{r.mobile}</span>
              <Badge variant={meta.variant} className="ml-auto">{meta.label}</Badge>
            </div>
            {r.errors.map((e, i) => (
              <p key={`e${i}`} className="pl-2 text-destructive">• {e}</p>
            ))}
            {r.warnings.map((w, i) => (
              <p key={`w${i}`} className="pl-2 text-muted-foreground">⚠ {w}</p>
            ))}
            {r.duplicate && (
              <p className="pl-2 text-muted-foreground">
                {r.status === "UPDATE"
                  ? `↳ updates existing ${r.duplicate.existing_cv_serial} (same mobile & email)`
                  : `↳ matches existing ${r.duplicate.existing_cv_serial} — sent to review`}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function BulkUploadDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [requirement, setRequirement] = useState("none");
  const [source, setSource] = useState("");
  const [preview, setPreview] = useState<BulkPreview | null>(null);
  const [result, setResult] = useState<BulkImportReport | null>(null);

  const sources = useSources();
  const previewMut = useBulkPreview();
  const importMut = useBulkImport();

  // Default the source to "Naukri" (this template is a Naukri export) once loaded.
  useEffect(() => {
    if (!source && sources.data?.length) {
      const naukri = sources.data.find((s) => s.source_name.toLowerCase() === "naukri");
      if (naukri) setSource(String(naukri.source_id));
    }
  }, [sources.data, source]);

  function resetOutputs() {
    setPreview(null);
    setResult(null);
  }

  async function onValidate() {
    if (!file) return;
    resetOutputs();
    try {
      const res = await previewMut.mutateAsync({ file });
      if (!res.ok) {
        toast.error(res.error ?? "Could not read the file.");
        return;
      }
      setPreview(res);
      const s = res.summary!;
      toast.success(`Validated ${s.total} rows: ${s.valid + s.update} importable, ${s.invalid} invalid`);
    } catch (e) {
      // Surface the exact backend reason (e.g. "File too large (max 5 MB).").
      toast.error(apiErrorMessage(e, "Validation failed. Ensure it's an .xlsx using the template."));
    }
  }

  async function onImport() {
    if (!file) return;
    try {
      const res = await importMut.mutateAsync({
        // Confirm the exact validated dataset from preview (draft); fall back to
        // the raw file only if no draft id was returned.
        batchId: preview?.batch_id ?? undefined,
        file: preview?.batch_id == null ? file ?? undefined : undefined,
        requirement: requirement !== "none" ? requirement : undefined,
        source: source || undefined,
      });
      if (!res.ok) {
        toast.error(res.error ?? "Import failed.");
        return;
      }
      setResult(res);
      toast.success(`Imported: ${res.created} created, ${res.updated} updated, ${res.possible_duplicates.length} to review`);
    } catch (e) {
      toast.error(apiErrorMessage(e, "Import failed."));
    }
  }

  function close() {
    setFile(null);
    setRequirement("none");
    resetOutputs();
    onOpenChange(false);
  }

  const importable = (preview?.summary?.valid ?? 0) + (preview?.summary?.update ?? 0);
  const previewRows = preview?.rows ?? [];
  const invalidRows = useMemo(() => previewRows.filter((r) => r.status === "INVALID"), [previewRows]);
  // Only VALID + UPDATE rows are actually imported — this matches the "Import N"
  // button and the Valid/Update badges. DUPLICATE rows go to review, so they get
  // their own group (previously they were mislabelled under "Importable rows").
  const okRows = useMemo(
    () => previewRows.filter((r) => r.status === "VALID" || r.status === "UPDATE"),
    [previewRows],
  );
  const duplicateRows = useMemo(() => previewRows.filter((r) => r.status === "DUPLICATE"), [previewRows]);
  const reportRows = result?.rows ?? previewRows;

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Bulk upload candidates</DialogTitle>
          <DialogDescription>
            Upload the mentor-approved template (or a Naukri "Candidate Details" export). Validate first, then import valid
            rows. Mobile is the unique key; duplicates go to the review queue.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => downloadCandidateTemplate()}>
              <Download className="h-4 w-4" /> Download sample template
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Excel file (.xlsx)</Label>
              <Input
                type="file"
                accept=".xlsx"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  resetOutputs();
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Source</Label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger><SelectValue placeholder="Select source" /></SelectTrigger>
                <SelectContent>
                  {(sources.data ?? []).map((s) => (
                    <SelectItem key={s.source_id} value={String(s.source_id)}>{s.source_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Add to requirement's review pool (optional)</Label>
              <RequirementSelect
                value={requirement === "none" ? "" : requirement}
                onChange={(id) => setRequirement(id || "none")}
                clearable
                clearLabel="No requirement"
                placeholder="Put imported candidates under review"
              />
            </div>
          </div>

          {/* Validation summary + preview */}
          {preview?.summary && !result && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <FileSpreadsheet className="h-4 w-4 text-primary" /> Validation summary
                <span className="ml-auto text-xs font-normal text-muted-foreground">header row {preview.header_row}</span>
              </div>
              {preview.duplicate_file && (
                <p className="flex items-center gap-1 rounded bg-warning/15 px-2 py-1 text-xs text-foreground">
                  <AlertTriangle className="h-3.5 w-3.5 text-warning" />
                  This exact file was already imported (batch #{preview.duplicate_file.batch_id}
                  {preview.duplicate_file.file_name ? ` · ${preview.duplicate_file.file_name}` : ""}). Importing again may
                  update the same candidates.
                </p>
              )}
              <SummaryChips s={preview.summary} />
              <p className="text-xs leading-relaxed text-muted-foreground">
                <span className="font-medium text-success">Will import</span> = new candidate ·{" "}
                <span className="font-medium text-primary">Update existing</span> = a candidate with the same mobile &amp; email already exists and its profile is refreshed from this row ·{" "}
                <span className="font-medium text-foreground">Duplicate</span> = same mobile but a different email → sent to the review queue
              </p>
              {invalidRows.length > 0 && (
                <div>
                  <p className="mb-1 flex items-center gap-1 text-xs font-medium text-destructive">
                    <XCircle className="h-3.5 w-3.5" /> Invalid rows (excluded from import)
                  </p>
                  <RowList rows={invalidRows} />
                </div>
              )}
              {duplicateRows.length > 0 && (
                <div>
                  <p className="mb-1 flex items-center gap-1 text-xs font-medium text-foreground">
                    <AlertTriangle className="h-3.5 w-3.5 text-warning" /> Duplicates — sent to review (not imported)
                  </p>
                  <RowList rows={duplicateRows} />
                </div>
              )}
              {okRows.length > 0 && (
                <div>
                  <p className="mb-1 flex items-center gap-1 text-xs font-medium text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Importable rows ({okRows.length})
                  </p>
                  <RowList rows={okRows} />
                </div>
              )}
            </div>
          )}

          {/* Import result */}
          {result && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <CheckCircle2 className="h-4 w-4 text-success" /> Import complete
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded bg-success/10 px-2 py-1 text-success">Created {result.created}</span>
                <span className="rounded bg-primary/10 px-2 py-1 text-primary">Updated {result.updated}</span>
                <span className="rounded bg-warning/15 px-2 py-1 text-foreground">To review {result.possible_duplicates.length}</span>
                <span className="rounded bg-destructive/10 px-2 py-1 text-destructive">Skipped {result.skipped.length}</span>
              </div>
              {result.skipped.length > 0 && (
                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                  <AlertTriangle className="h-3.5 w-3.5" /> Skipped rows are listed in the downloadable report.
                </p>
              )}
            </div>
          )}
        </DialogBody>

        <DialogFooter className="flex-wrap gap-2">
          {(preview || result) && (
            <Button variant="outline" size="sm" onClick={() => downloadErrorReport(reportRows)}>
              <Copy className="h-4 w-4" /> Download report
            </Button>
          )}
          <Button variant="ghost" onClick={close} className="ml-auto">
            {result ? "Done" : "Cancel"}
          </Button>
          {!preview && !result && (
            <Button onClick={onValidate} disabled={!file || previewMut.isPending}>
              {previewMut.isPending ? "Validating…" : "Validate"}
            </Button>
          )}
          {preview && !result && (
            <Button onClick={onImport} disabled={importable === 0 || importMut.isPending}>
              {importMut.isPending ? "Importing…" : `Import ${importable} valid row${importable === 1 ? "" : "s"}`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
