// import type { ColumnDef } from "@tanstack/react-table";
// import { Pencil } from "lucide-react";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import { candidateStatusLabel, candidateStatusVariant } from "@/lib/status";
// import { fmtDate } from "@/lib/format";
// import type { Candidate } from "./types";

// function expLabel(min: string | null, max: string | null) {
//   if (min && max) return `${min}–${max}`;
//   return min ?? max ?? "—";
// }

// // export const candidateColumns: ColumnDef<Candidate>[] = [

// const baseCandidateColumns: ColumnDef<Candidate>[] = [
//   {
//     accessorKey: "cv_serial",
//     header: "CV",
//     cell: ({ row }) => <span className="font-medium">{row.original.cv_serial}</span>,
//   },
//   {
//     accessorKey: "candidate_name",
//     header: "Candidate",
//     cell: ({ row }) => (
//       <div className="min-w-0">
//         <div className="font-medium">{row.original.candidate_name}</div>
//         <div className="text-xs text-muted-foreground">{row.original.email}</div>
//       </div>
//     ),
//   },
//   { accessorKey: "mobile", header: "Mobile" },
//   {
//     id: "experience",
//     header: "Exp (yrs)",
//     enableSorting: false,
//     cell: ({ row }) => <span className="tabular-nums">{expLabel(row.original.exp_min, row.original.exp_max)}</span>,
//   },
//   {
//     id: "location",
//     accessorFn: (r) => r.current_location_name ?? "",
//     header: "Location",
//     cell: ({ row }) => <span>{row.original.current_location_name ?? "—"}</span>,
//   },
//   {
//     id: "skills",
//     header: "Skills",
//     enableSorting: false,
//     cell: ({ row }) => (
//       <span className="text-xs text-muted-foreground">{row.original.skill_names.join(", ") || "—"}</span>
//     ),
//   },
//   {
//     accessorKey: "candidate_status_name",
//     header: "Candidate Status",
//     cell: ({ row }) =>
//       row.original.candidate_status_name ? (
//         <Badge variant={candidateStatusVariant(row.original.candidate_status_code)}>
//           {candidateStatusLabel(row.original.candidate_status_code, row.original.candidate_status_name)}
//         </Badge>
//       ) : (
//         <span className="text-muted-foreground">—</span>
//       ),
//   },
//   {
//     accessorKey: "created_on",
//     header: "Added",
//     cell: ({ row }) => <span className="text-muted-foreground">{fmtDate(row.original.created_on)}</span>,
//   },
// ];


// export function candidateColumns(opts?: { onEdit?: (candidate: Candidate) => void }): ColumnDef<Candidate>[] {
//   if (!opts?.onEdit) return baseCandidateColumns;
//   return [
//     ...baseCandidateColumns,
//     {
//       id: "actions",
//       header: "",
//       enableSorting: false,
//       cell: ({ row }) => (
//         <Button
//           variant="ghost"
//           size="icon"
//           className="h-8 w-8"
//           title="Edit candidate"
//           onClick={(e) => {
//             e.stopPropagation();
//             opts.onEdit!(row.original);
//           }}
//         >
//           <Pencil className="h-4 w-4" />
//         </Button>
//       ),
//     },
//   ];
// }


import type { ColumnDef } from "@tanstack/react-table";
import { Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { candidateStatusLabel, candidateStatusVariant } from "@/lib/status";
import { fmtDate } from "@/lib/format";
import type { Candidate } from "./types";

function expLabel(min: string | null, max: string | null) {
  if (min && max) return `${min}–${max}`;
  return min ?? max ?? "—";
}

const baseCandidateColumns: ColumnDef<Candidate>[] = [
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

/** Candidate list columns. Pass `onEdit` (Administrator/Recruiter only — the
 * caller gates this) to append an Edit action that reopens the Add Candidate
 * form pre-populated with this candidate's data. */
export function candidateColumns(opts?: { onEdit?: (candidate: Candidate) => void }): ColumnDef<Candidate>[] {
  if (!opts?.onEdit) return baseCandidateColumns;
  return [
    ...baseCandidateColumns,
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          title="Edit candidate"
          onClick={(e) => {
            e.stopPropagation();
            opts.onEdit!(row.original);
          }}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      ),
    },
  ];
}