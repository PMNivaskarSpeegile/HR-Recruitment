import { useState } from "react";
import { GripVertical, MapPin, Plus } from "lucide-react";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLocations } from "@/lib/lookups";
import { apiErrorMessage } from "@/lib/apiError";
import { useAuth } from "@/auth/AuthContext";
import { MasterCreateDialog } from "@/components/form/MasterCreateDialog";
import { useUnmappedLocations, useReconcileLocation } from "./api";

// Normalize a city string for matching an unmapped text to a created location —
// mirrors the backend rule (NFKC, trim, collapse spaces, case-insensitive).
function normLoc(s: string) {
  return s.normalize("NFKC").replace(/\s+/g, " ").trim().toLowerCase();
}

export function UnmappedLocationsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const unmapped = useUnmappedLocations(open); // only fetch while open
  const locations = useLocations();
  const reconcile = useReconcileLocation();
  const { user } = useAuth();
  // Adding to Location Master is Admin-only (Master Data CRUD). Recruiters may
  // only map to existing locations.
  const isAdmin = user?.role.code === "ADM";
  const [addOpen, setAddOpen] = useState(false);
  const [picked, setPicked] = useState<Record<string, string>>({});
  // The unmapped text the admin last dragged onto the City field — its intent for
  // the location being created, so we reconcile exactly that text on save.
  const [draggedText, setDraggedText] = useState<string | null>(null);
  const rows = unmapped.data ?? [];

  const selectedFor = (r: { text: string; suggested_location_id: number | null }) =>
    picked[r.text] ?? (r.suggested_location_id != null ? String(r.suggested_location_id) : "");

  function onMap(r: { text: string; suggested_location_id: number | null }) {
    const chosen = selectedFor(r);
    if (!chosen) {
      toast.error("Pick a city to map to.");
      return;
    }
    reconcile.mutate(
      { text: r.text, location_id: Number(chosen) },
      {
        onSuccess: (res) =>
          toast.success(`Mapped "${r.text}" → ${res.location} (${res.reconciled} candidate${res.reconciled === 1 ? "" : "s"})`),
        onError: (e) => toast.error(apiErrorMessage(e, "Could not map this location.")),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><MapPin className="h-4 w-4" /> Unmapped locations</DialogTitle>
          <DialogDescription>
            Imported locations kept as text (not in Location Master). Map each to an existing city — or add the city to
            Master Data first, then map. All candidates with that text are linked and the text cleared.
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {isAdmin && (
            <div className="mb-3 flex justify-end">
              <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
                <Plus className="h-4 w-4" /> Add Location
              </Button>
            </div>
          )}
          {unmapped.isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
              No unmapped locations. 🎉
            </p>
          ) : (
            <ul className="divide-y">
              {rows.map((r) => (
                <li key={r.text} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
                  <span className="font-medium">{r.text}</span>
                  <Badge variant="muted">{r.count} candidate{r.count === 1 ? "" : "s"}</Badge>
                  {r.suggested_city && (
                    <span className="text-xs text-muted-foreground">suggested: {r.suggested_city}</span>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    <Select value={selectedFor(r)} onValueChange={(v) => setPicked((p) => ({ ...p, [r.text]: v }))}>
                      <SelectTrigger className="h-9 w-48"><SelectValue placeholder="Map to city…" /></SelectTrigger>
                      <SelectContent>
                        {(locations.data ?? []).map((l) => (
                          <SelectItem key={l.location_id} value={String(l.location_id)}>
                            {l.city}, {l.state}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button size="sm" disabled={!selectedFor(r) || reconcile.isPending} onClick={() => onMap(r)}>
                      Map
                    </Button>
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

      {/* Admin-only: create a missing city in Location Master WITHOUT leaving the
          reconciliation flow. On save the location cache refreshes, so it appears
          in the map-to dropdowns immediately; a matching unmapped row is pre-picked.
          The aside is a read-only reminder of which cities still need adding. */}
      {isAdmin && (
        <MasterCreateDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          configKey="locations"
          allowMultiple
          dropTargetField="city"
          onCreated={(loc) => {
            const created = `${loc.city}, ${loc.state}`;
            const cityNorm = normLoc(String(loc.city ?? ""));
            // Reconcile the text the admin dragged in (their intent), plus any
            // unmapped rows whose normalized text equals the new city.
            const targets = new Set<string>();
            if (draggedText && rows.some((r) => r.text === draggedText)) targets.add(draggedText);
            for (const r of rows) if (normLoc(r.text) === cityNorm) targets.add(r.text);
            setDraggedText(null);
            if (targets.size === 0) {
              toast.success(`"${created}" added to Location Master — now available to map.`);
              return;
            }
            // Each reconcile invalidates the unmapped list + candidate queries, so
            // the mapped city drops out of the list and its count updates live.
            Promise.all(
              [...targets].map((text) => reconcile.mutateAsync({ text, location_id: loc.location_id })),
            )
              .then((results) => {
                const total = results.reduce((n, res) => n + (res?.reconciled ?? 0), 0);
                toast.success(`"${created}" added — mapped ${total} candidate${total === 1 ? "" : "s"}.`);
              })
              .catch((e) => toast.error(apiErrorMessage(e, "Location added, but reconciliation failed.")));
          }}
          aside={
            <div>
              <p className="mb-1 font-medium text-foreground">Unmapped locations</p>
              {rows.length === 0 ? (
                <p className="text-muted-foreground">None 🎉</p>
              ) : (
                <>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Drag a city onto the <span className="font-medium">City</span> field — you can edit it before saving.
                  </p>
                  <ul className="space-y-1">
                    {rows.map((r) => (
                      <li
                        key={r.text}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("text/plain", r.text);
                          e.dataTransfer.effectAllowed = "copy";
                          setDraggedText(r.text);
                        }}
                        title="Drag onto the City field"
                        className="flex cursor-grab items-center gap-1.5 rounded-md border bg-background px-2 py-1.5 text-sm active:cursor-grabbing hover:border-primary hover:bg-accent/50"
                      >
                        <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 truncate">{r.text}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">{r.count}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          }
        />
      )}
    </Dialog>
  );
}
