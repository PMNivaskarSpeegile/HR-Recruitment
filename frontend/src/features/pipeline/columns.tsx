import type { ColumnDef } from "@tanstack/react-table";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Candidate } from "@/features/candidates/types";

function expLabel(min: string | null, max: string | null) {
  if (min && max) return `${min}–${max}`;
  return min ?? max ?? "—";
}

export function buildNewCvColumns(opts: {
  onVerify: (candidate: Candidate) => void;
}): ColumnDef<Candidate>[] {
  return [
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
      id: "skills",
      header: "Skills",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{row.original.skill_names.join(", ") || "—"}</span>
      ),
    },
    {
      id: "match",
      header: "Match",
      accessorFn: (r) => r.skill_match_pct ?? 0,
      cell: ({ row }) => {
        const matched = row.original.matched_skills ?? 0;
        const required = row.original.required_skills ?? 0;
        const pct = row.original.skill_match_pct ?? 0;
        if (!required) return <span className="text-muted-foreground">—</span>;
        const variant = pct >= 67 ? "success" : pct >= 34 ? "warning" : "muted";
        return (
          <div className="flex items-center gap-2">
            <Badge variant={variant}>{pct}%</Badge>
            <span className="text-xs tabular-nums text-muted-foreground">
              {matched}/{required} skills
            </span>
          </div>
        );
      },
    },
    {
      id: "verify",
      header: "",
      enableSorting: false,
      enableHiding: false,
      cell: ({ row }) => (
        <div className="text-right">
          {/* Verification + the Shortlist / Not Suitable / Fake / Blacklist / Save
              decision happen together, in the context of this requirement. */}
          <Button size="sm" onClick={() => opts.onVerify(row.original)}>
            <ShieldCheck className="h-4 w-4" /> Verify &amp; Update Profile
          </Button>
        </div>
      ),
    },
  ];
}
