import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchReferences, useResourceList, useResourceMutations } from "./api";
import type { ReferenceInfo, ResourceRow } from "./api";
import type { ResourceConfig } from "./config";
import { ResourceForm } from "./ResourceForm";

/** Pull a human message out of the API error envelope. */
function errorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: any } })?.response?.data;
  const body = data?.error ?? data;
  if (body?.code === "stale") return "This record was changed by someone else. Reload and try again.";
  if (typeof body?.detail === "string") return body.detail;
  if (body && typeof body === "object") {
    const first = Object.values(body)[0];
    if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    if (typeof first === "string") return first;
  }
  return fallback;
}

/**
 * Full CRUD manager for one master resource: searchable table + add/edit form
 * (shared `ResourceForm` validation) + two-tier delete (deactivate always;
 * permanent delete only when unreferenced). Used by the Master Data page for
 * the selected resource and, as a lightweight embedded section, for Domains
 * inside the Skill master.
 */
export function ResourceManager({
  config,
  heading,
  description,
}: {
  config: ResourceConfig;
  /** When set, renders a compact titled section (used for Domains under Skills). */
  heading?: string;
  description?: string;
}) {
  const list = useResourceList(config.endpoint);
  const rows = list.data ?? [];
  const { create, update, remove, purge } = useResourceMutations(config.endpoint, config.pk);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ResourceRow | null>(null);
  const [deleting, setDeleting] = useState<ResourceRow | null>(null);
  const [refs, setRefs] = useState<ReferenceInfo | null>(null);
  const [refsLoading, setRefsLoading] = useState(false);

  useEffect(() => {
    if (!deleting) {
      setRefs(null);
      return;
    }
    setRefsLoading(true);
    fetchReferences(config.endpoint, deleting[config.pk])
      .then(setRefs)
      .catch(() => setRefs(null))
      .finally(() => setRefsLoading(false));
  }, [deleting, config.endpoint, config.pk]);

  async function handleCreate(values: ResourceRow) {
    try {
      await create.mutateAsync(values);
      toast.success(`${config.singular} created`);
      setFormOpen(false);
    } catch (err) {
      toast.error(errorMessage(err, "Could not create — check the highlighted fields."));
    }
  }
  async function handleUpdate(values: ResourceRow) {
    try {
      await update.mutateAsync(values);
      toast.success(`${config.singular} updated`);
      setFormOpen(false);
    } catch (err) {
      toast.error(errorMessage(err, "Could not update the record."));
    }
  }
  async function handleReactivate(row: ResourceRow) {
    try {
      await update.mutateAsync({
        [config.pk]: row[config.pk],
        is_active: true,
        expected_updated_on: row.updated_on ?? row.created_on ?? null,
      });
      toast.success(`${config.singular} reactivated`);
      setFormOpen(false);
    } catch (err) {
      toast.error(errorMessage(err, "Could not reactivate the record."));
    }
  }
  async function handleDeactivate() {
    if (!deleting) return;
    try {
      await remove.mutateAsync(deleting[config.pk]);
      toast.success(`${config.singular} deactivated`);
      setDeleting(null);
    } catch (err) {
      toast.error(errorMessage(err, "Could not deactivate the record."));
    }
  }
  async function handlePermanentDelete() {
    if (!deleting) return;
    try {
      await purge.mutateAsync(deleting[config.pk]);
      toast.success(`${config.singular} permanently deleted`);
      setDeleting(null);
    } catch (err) {
      toast.error(errorMessage(err, "Could not delete — it is referenced elsewhere."));
    }
  }

  const columns: ColumnDef<ResourceRow>[] = [
    ...config.columns.map((c) => ({
      accessorKey: c.key,
      header: c.header,
      cell: ({ row }: { row: { original: ResourceRow } }) => <span>{row.original[c.key] || "—"}</span>,
    })),
    {
      id: "status",
      header: "Status",
      cell: ({ row }: { row: { original: ResourceRow } }) =>
        row.original.is_active ? <Badge variant="success">Active</Badge> : <Badge variant="muted">Inactive</Badge>,
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      enableHiding: false,
      cell: ({ row }: { row: { original: ResourceRow } }) => (
        <div className="flex justify-end gap-1">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => {
              setEditing(row.original);
              setFormOpen(true);
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="text-destructive" onClick={() => setDeleting(row.original)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  const referenced = !!refs?.referenced;
  const refSummary = refs?.details.map((d) => `${d.count} ${d.entity}`).join(", ");

  const addButton = (
    <Button
      size="sm"
      onClick={() => {
        setEditing(null);
        setFormOpen(true);
      }}
    >
      <Plus className="h-4 w-4" />
      Add {config.singular}
    </Button>
  );

  return (
    <div>
      {heading && (
        <div className="mb-3">
          <h2 className="text-lg font-semibold">{heading}</h2>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        isLoading={list.isLoading}
        searchPlaceholder={`Search ${config.label.toLowerCase()}…`}
        emptyMessage={`No ${config.label.toLowerCase()} yet.`}
        toolbar={addButton}
      />

      <ResourceForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        config={config}
        initial={editing}
        rows={rows}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        onReactivate={handleReactivate}
        saving={create.isPending || update.isPending}
      />

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete {config.singular}</DialogTitle>
            <DialogDescription>
              {refsLoading
                ? "Checking where this record is used…"
                : referenced
                  ? `This record is used by ${refSummary}. It can be deactivated (hidden from new selections; existing records keep working) but not permanently deleted.`
                  : "This record isn't referenced anywhere. You can deactivate it, or permanently remove it."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:justify-between">
            <Button variant="outline" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <div className="flex gap-2">
              {deleting?.is_active !== false && (
                <Button variant="secondary" onClick={handleDeactivate} disabled={remove.isPending}>
                  Deactivate
                </Button>
              )}
              <Button
                variant="destructive"
                onClick={handlePermanentDelete}
                disabled={refsLoading || referenced || purge.isPending}
                title={referenced ? "Referenced by other records — deactivate instead." : undefined}
              >
                Delete permanently
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
