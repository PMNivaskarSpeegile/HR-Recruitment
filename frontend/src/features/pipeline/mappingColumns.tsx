import type { ColumnDef } from "@tanstack/react-table";
import { ChevronDown, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { statusVariant } from "@/lib/status";
import { actionLabel } from "@/lib/workflow";
import { fmtDateTime } from "@/lib/format";
import type { Mapping } from "./types";

export interface MappingActions {
  stage: string;
  onSendJd: (m: Mapping) => void;
  onTransition: (m: Mapping, toStatus: string) => void;
  onScreenings: (m: Mapping) => void;
}

function ActionCell({ m, actions }: { m: Mapping; actions: MappingActions }) {
  if (actions.stage === "SHORTLISTED") {
    return (
      <Button size="sm" onClick={() => actions.onSendJd(m)}>
        {actionLabel("SEND_JD")}
      </Button>
    );
  }
  if (actions.stage === "JD_EMAIL_SENT") {
    // Only two actions here: Schedule Screening (advances to Screening Scheduled)
    // and Drop (close). No "No Response" outcome at this stage — see diagram.
    return (
      <div className="flex items-center justify-end gap-2">
        <Button size="sm" onClick={() => actions.onScreenings(m)}>
          {actionLabel("SCHEDULE_SCREENING")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="text-destructive hover:text-destructive"
          onClick={() => actions.onTransition(m, "DROPPED")}
        >
          {actionLabel("DROPPED")}
        </Button>
      </div>
    );
  }
  if (actions.stage === "SCREENING_SCHEDULED") {
    // Everything for this stage lives in the Screenings popup: Reschedule at the
    // top, and a Record Outcome dropdown that sets the application outcome
    // (OK to Proceed advances; No Response / Drop / Reject / Mark Fake / Blacklist
    // close). No standalone Outcome button on the row.
    return (
      <Button size="sm" variant="outline" onClick={() => actions.onScreenings(m)}>
        Screenings
      </Button>
    );
  }
  if (actions.stage === "OK_TO_PROCEED") {
    // Release Offer advances to Offer Released; the rest close the application.
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm">
            Outcome <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => actions.onTransition(m, "OFFERED")}>{actionLabel("OFFERED")}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => actions.onTransition(m, "REJECTED")}>{actionLabel("REJECTED")}</DropdownMenuItem>
          <DropdownMenuItem onClick={() => actions.onTransition(m, "DROPPED")}>{actionLabel("DROPPED")}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => actions.onTransition(m, "FAKE")}
            className="text-destructive focus:text-destructive"
          >
            {actionLabel("FAKE")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
  if (actions.stage === "OFFERED") {
    // Offer Released → Offer Accepted (→ Awaiting Joining) | Offer Declined (close).
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm">
            Outcome <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => actions.onTransition(m, "AWAITING_JOINING")}>
            {actionLabel("AWAITING_JOINING")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => actions.onTransition(m, "OFFER_DECLINED")}
            className="text-destructive focus:text-destructive"
          >
            {actionLabel("OFFER_DECLINED")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
  if (actions.stage === "AWAITING_JOINING") {
    // Joined completes the hire (consumes one Open seat); Withdraw closes it.
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm">
            Outcome <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => actions.onTransition(m, "JOINED")}>{actionLabel("JOINED")}</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => actions.onTransition(m, "WITHDRAWN")}
            className="text-destructive focus:text-destructive"
          >
            {actionLabel("WITHDRAWN")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
  return null;
}

export function buildMappingColumns(actions: MappingActions): ColumnDef<Mapping>[] {
  const columns: ColumnDef<Mapping>[] = [
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
      id: "outcome",
      header: "Latest outcome",
      enableSorting: false,
      cell: ({ row }) =>
        row.original.latest_outcome_name ? (
          <Badge variant={statusVariant(row.original.latest_outcome_name)}>
            {row.original.latest_outcome_name}
          </Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "recruiter",
      header: "Recruiter",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-muted-foreground">{row.original.recruiter_name ?? "—"}</span>
      ),
    },
    {
      id: "updated",
      header: "Last updated",
      enableSorting: false,
      // The active tab already tells you the stage; show recency instead.
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {fmtDateTime(row.original.updated_on ?? row.original.created_on)}
        </span>
      ),
    },
  ];

  if (actions.stage === "SCREENING_SCHEDULED") {
    columns.push({
      id: "screening",
      header: "Screening",
      enableSorting: false,
      cell: ({ row }) => {
        const m = row.original;
        if (!m.screening_mode_name && !m.screening_datetime) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <span className="whitespace-nowrap text-muted-foreground">
            {m.screening_mode_name && <span className="font-medium text-foreground">{m.screening_mode_name}</span>}
            {m.screening_mode_name && m.screening_datetime ? " · " : ""}
            {fmtDateTime(m.screening_datetime)}
          </span>
        );
      },
    });
  }

  columns.push({
    id: "actions",
    header: "",
    enableSorting: false,
    enableHiding: false,
    cell: ({ row }) => (
      <div className="flex items-center justify-end gap-2">
        {/* Once a candidate is in the pipeline they are already verified & shortlisted.
            Verification/profile edits happen only before entering the pipeline (in the
            "Candidates to review" pool), so this is a non-clickable status badge. */}
        <Badge variant="success" className="gap-1" title="Verified before shortlisting">
          <ShieldCheck className="h-3 w-3" /> Verified
        </Badge>
        {!row.original.is_closed && <ActionCell m={row.original} actions={actions} />}
      </div>
    ),
  });

  return columns;
}
