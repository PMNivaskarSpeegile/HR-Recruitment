import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/badge";
import { candidateStatusLabel, candidateStatusVariant } from "@/lib/status";
import { fmtDate } from "@/lib/format";
import type { Candidate } from "./types";

function expLabel(min: string | null, max: string | null) {
  if (min && max) return `${min}–${max}`;
  return min ?? max ?? "—";
}

export const candidateColumns: ColumnDef<Candidate>[] = [
  {
    accessorKey: "cv_serial",
    header: "CV",
    cell: ({ row }) => <span className="font-medium">{row.original.cv_serial}</span>,
  },
  {
    accessorKey: "candidate_name",
    header: "Candidate",
    cell: ({ row }) => (
      <div className="min-w-0">
        <div className="font-medium">{row.original.candidate_name}</div>
        <div className="text-xs text-muted-foreground">{row.original.email}</div>
      </div>
    ),
  },
  { accessorKey: "mobile", header: "Mobile" },
  {
    id: "experience",
    header: "Exp (yrs)",
    enableSorting: false,
    cell: ({ row }) => <span className="tabular-nums">{expLabel(row.original.exp_min, row.original.exp_max)}</span>,
  },
  {
    id: "location",
    accessorFn: (r) => r.current_location_name ?? "",
    header: "Location",
    cell: ({ row }) => <span>{row.original.current_location_name ?? "—"}</span>,
  },
  {
    id: "skills",
    header: "Skills",
    enableSorting: false,
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground">{row.original.skill_names.join(", ") || "—"}</span>
    ),
  },
  {
    accessorKey: "candidate_status_name",
    header: "Candidate Status",
    cell: ({ row }) =>
      row.original.candidate_status_name ? (
        <Badge variant={candidateStatusVariant(row.original.candidate_status_code)}>
          {candidateStatusLabel(row.original.candidate_status_code, row.original.candidate_status_name)}
        </Badge>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    accessorKey: "created_on",
    header: "Added",
    cell: ({ row }) => <span className="text-muted-foreground">{fmtDate(row.original.created_on)}</span>,
  },
];
