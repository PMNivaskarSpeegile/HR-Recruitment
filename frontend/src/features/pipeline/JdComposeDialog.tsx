import { useEffect, useState } from "react";
import { Mail, Pencil } from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useJdPreview, useSendJd } from "./api";
import type { JdPreviewRecipient } from "./api";
import type { Mapping } from "./types";

/**
 * UC4 — compose & preview the JD email before sending. The body/subject come
 * from the admin-editable JD template (rendered server-side, the same render
 * path as the actual send), so "what you preview is what's sent". Editing the
 * template itself happens in Admin → Email Templates.
 */
export function JdComposeDialog({
  reqId,
  mappings,
  open,
  onClose,
}: {
  reqId: string;
  mappings: Mapping[];
  open: boolean;
  onClose: () => void;
}) {
  const preview = useJdPreview();
  const sendJd = useSendJd();
  const previewMutate = preview.mutate;

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [focused, setFocused] = useState<number | null>(null);

  // When the dialog opens, render the preview for every candidate in scope.
  useEffect(() => {
    if (!open || mappings.length === 0) return;
    const ids = mappings.map((m) => m.mapping_id);
    setSelected(new Set(ids));
    setFocused(ids[0] ?? null);
    previewMutate({ requirement: Number(reqId), mapping_ids: ids });
  }, [open, mappings, reqId, previewMutate]);

  const recipients: JdPreviewRecipient[] = preview.data?.recipients ?? [];
  const focusedRecipient = recipients.find((r) => r.mapping_id === focused) ?? recipients[0];

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function send() {
    const ids = recipients.map((r) => r.mapping_id).filter((id) => selected.has(id));
    if (ids.length === 0) {
      toast.error("Select at least one candidate.");
      return;
    }
    sendJd.mutate(
      { requirement: Number(reqId), mapping_ids: ids },
      {
        onSuccess: (report: { sent: number; failed: unknown[] }) => {
          const failed = report.failed?.length ?? 0;
          if (report.sent) toast.success(`JD emailed to ${report.sent} candidate${report.sent === 1 ? "" : "s"}.`);
          if (failed) toast.error(`${failed} email${failed === 1 ? "" : "s"} failed to send.`);
          onClose();
        },
        onError: () => toast.error("Could not send the JD email."),
      }
    );
  }

  const selectedCount = recipients.filter((r) => selected.has(r.mapping_id)).length;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-primary" /> Compose JD email
          </DialogTitle>
          <DialogDescription>
            Review the message, choose recipients, and send. Content is driven by the{" "}
            <span className="font-medium">JD email template</span> — edit it in Admin → Email Templates.
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
        {preview.isError ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load the preview. Ensure an active <span className="font-mono">JD_EMAIL</span> template exists in
            Admin → Email Templates.
          </div>
        ) : (
          <div className="grid grid-cols-[minmax(0,260px)_1fr] gap-4">
            {/* Recipients */}
            <div className="min-w-0">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Recipients ({selectedCount}/{recipients.length})
              </div>
              <div className="max-h-[22rem] space-y-1 overflow-y-auto pr-1">
                {preview.isPending
                  ? Array.from({ length: Math.min(mappings.length || 3, 5) }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))
                  : recipients.map((r) => (
                      <button
                        key={r.mapping_id}
                        type="button"
                        onClick={() => setFocused(r.mapping_id)}
                        className={cn(
                          "flex w-full items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                          focused === r.mapping_id ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted"
                        )}
                      >
                        <Checkbox
                          checked={selected.has(r.mapping_id)}
                          onCheckedChange={() => toggle(r.mapping_id)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5"
                        />
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">{r.candidate_name}</span>
                          <span className="block truncate text-xs text-muted-foreground">{r.recipient}</span>
                        </span>
                      </button>
                    ))}
              </div>
            </div>

            {/* Preview */}
            <div className="min-w-0 rounded-lg border bg-muted/30">
              {preview.isPending ? (
                <div className="space-y-3 p-4">
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-40 w-full" />
                </div>
              ) : focusedRecipient ? (
                <div className="flex h-full flex-col">
                  <div className="border-b bg-background/60 px-4 py-3">
                    <div className="text-xs text-muted-foreground">Subject</div>
                    <div className="font-medium">{focusedRecipient.subject}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      To: <span className="text-foreground">{focusedRecipient.recipient}</span>
                    </div>
                  </div>
                  <pre className="max-h-[18rem] overflow-y-auto whitespace-pre-wrap px-4 py-3 font-sans text-sm leading-relaxed">
                    {focusedRecipient.body}
                  </pre>
                </div>
              ) : (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  No shortlisted candidates to email.
                </div>
              )}
            </div>
          </div>
        )}
        </DialogBody>

        <DialogFooter className="items-center sm:justify-between">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Pencil className="h-3.5 w-3.5" /> Same template renders every email.
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={send} disabled={sendJd.isPending || preview.isPending || selectedCount === 0}>
              {sendJd.isPending ? "Sending…" : `Send to ${selectedCount} candidate${selectedCount === 1 ? "" : "s"}`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
