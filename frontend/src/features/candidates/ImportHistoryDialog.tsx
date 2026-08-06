import { Download, Undo2, History } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { fmtDateTime } from "@/lib/format";
import { apiErrorMessage } from "@/lib/apiError";
import { useImportBatches, useRollbackImportBatch, downloadBatchReport } from "./api";
import type { ImportBatch } from "./api";

const STATUS_VARIANT: Record<ImportBatch["status"], "success" | "muted" | "danger" | "warning"> = {
  COMPLETED: "success",
  PENDING: "warning",
  FAILED: "danger",
  ROLLED_BACK: "muted",
};

export function ImportHistoryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const batches = useImportBatches();
  const rollback = useRollbackImportBatch();
  const rows = batches.data?.results ?? [];

  function onRollback(b: ImportBatch) {
    if (!window.confirm(
      `Roll back import #${b.batch_id}? This removes candidates it created that are still untouched ` +
      `(New CV, not in any pipeline). Worked candidates are kept.`
    )) return;
    rollback.mutate(
      { id: b.batch_id },
      {
        onSuccess: (res) => toast.success(`Rolled back: ${res.removed_count} removed, ${res.kept_count} kept`),
        onError: (e) => toast.error(apiErrorMessage(e, "Could not roll back this import.")),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><History className="h-4 w-4" /> Import history</DialogTitle>
          <DialogDescription>Your bulk uploads (admins see all). Download the report or roll back an import.</DialogDescription>
        </DialogHeader>

        <DialogBody>
          {batches.isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
              No bulk imports yet.
            </p>
          ) : (
            <ul className="divide-y">
              {rows.map((b) => (
                <li key={b.batch_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3 text-sm">
                  <span className="font-medium tabular-nums">#{b.batch_id}</span>
                  <span className="text-muted-foreground">{fmtDateTime(b.created_on)}</span>
                  <span className="min-w-0 truncate">{b.file_name ?? "—"}</span>
                  <span className="text-xs text-muted-foreground">by {b.uploaded_by_name ?? "—"}</span>
                  <Badge variant={STATUS_VARIANT[b.status]}>{b.status.replace("_", " ").toLowerCase()}</Badge>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <span className="rounded bg-success/10 px-1.5 py-0.5 text-success">+{b.created_count}</span>
                    <span className="rounded bg-primary/10 px-1.5 py-0.5 text-primary">~{b.updated_count}</span>
                    <span className="rounded bg-warning/15 px-1.5 py-0.5">dup {b.duplicate_count}</span>
                    <span className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">skip {b.skipped_count}</span>
                  </div>
                  <div className="ml-auto flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => downloadBatchReport(b.batch_id)}>
                      <Download className="h-3.5 w-3.5" /> Report
                    </Button>
                    {b.status === "COMPLETED" && b.created_count > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        disabled={rollback.isPending}
                        onClick={() => onRollback(b)}
                      >
                        <Undo2 className="h-3.5 w-3.5" /> Roll back
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} className="ml-auto">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
