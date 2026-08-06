import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle, Ban, CalendarClock, Eye, MoreVertical, Pencil, UserPlus } from "lucide-react";
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
import { fmtDate } from "@/lib/format";
import type { Requirement } from "./types";

// Requirement statuses that are no longer being worked — an Overdue warning on
// these is meaningless, and they can't be Edited. (Expired is a derived overlay,
// not a stored status — handled separately via `is_expired`.)
const TERMINAL_STATUS_CODES = new Set(["CLOSE_FILLED", "CLOSE_LOST", "CANCELLED"]);

/** True when a requirement has passed its Target Closing Date and is still open.
 *  No target date → never overdue; closed requirements → never overdue. */
export function isRequirementOverdue(targetDate: string | null | undefined, statusCode: string): boolean {
  if (!targetDate || TERMINAL_STATUS_CODES.has(statusCode)) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${targetDate}T00:00:00`);
  return target.getTime() < today.getTime();
}

const OVERDUE_TOOLTIP =
  "This requirement has passed its Target Closing Date. Please review, extend the target date, or close the requirement.";

/** Amber ⚠ "Overdue" pill — informational only; hover shows guidance. */
export function OverdueBadge() {
  return (
    <span
      title={OVERDUE_TOOLTIP}
      className="inline-flex items-center gap-1 rounded-full border border-transparent bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
    >
      <AlertTriangle className="h-3 w-3" /> Overdue
    </span>
  );
}

// Manual status transitions available to HM/Admin, by current status code.
// `danger` items get a destructive style. Cancel is confirmed by the caller.
type StatusAction = { label: string; to: string; danger?: boolean };
export function manualStatusActions(code: string): StatusAction[] {
  switch (code) {
    // All active states share the same lifecycle actions — a recruiter
    // assignment doesn't remove the HM's ability to Hold/Cancel.
    case "ASSIGNED":
    case "OPEN":
    case "PARTIAL_FILLED":
      return [
        { label: "Put on Hold", to: "HOLD" },
        { label: "Cancel Requirement", to: "CANCELLED", danger: true },
        { label: "Close as Lost", to: "CLOSE_LOST", danger: true },
      ];
    case "HOLD":
      return [
        { label: "Resume Requirement", to: "OPEN" },
        { label: "Cancel Requirement", to: "CANCELLED", danger: true },
        { label: "Close as Lost", to: "CLOSE_LOST", danger: true },
      ];
    case "CANCELLED":
      return [{ label: "Reopen Requirement", to: "OPEN" }];
    // CLOSE_LOST is terminal — no reopen.
    default:
      return [];
  }
}

export function buildRequirementColumns(opts?: {
  onView?: (r: Requirement) => void;
  onEdit?: (r: Requirement) => void;
  onAssign?: (r: Requirement) => void; // Admin only — page passes it only for admins
  onSetStatus?: (r: Requirement, toStatus: string) => void;
  onEndRecruitment?: (r: Requirement) => void; // HM only — expired + partially filled
  onExtendDate?: (r: Requirement) => void; // HM only — expired (restores recruitment)
}): ColumnDef<Requirement>[] {
  const columns: ColumnDef<Requirement>[] = [
    {
      accessorKey: "req_tracker_no",
      header: "Tracker",
      cell: ({ row }) => <span className="font-medium">{row.original.req_tracker_no}</span>,
    },
    {
      accessorKey: "jd_role_name",
      header: "Role",
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="font-medium">{row.original.jd_role_name}</div>
          <div className="text-xs text-muted-foreground">{row.original.client_name}</div>
        </div>
      ),
    },
    { accessorKey: "req_type_name", header: "Type" },
    {
      id: "recruiter",
      accessorFn: (r) => r.recruiter_name ?? "",
      header: "Recruiter",
      cell: ({ row }) =>
        row.original.recruiter_name ? (
          <span>{row.original.recruiter_name}</span>
        ) : (
          <span className="text-muted-foreground">Unassigned</span>
        ),
    },
    {
      id: "positions",
      header: "Positions",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="tabular-nums">
          {row.original.positions_filled}/{row.original.positions_open}
        </span>
      ),
    },
    {
      accessorKey: "req_status_name",
      header: "Status",
      cell: ({ row }) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={statusVariant(row.original.req_status_name)}>{row.original.req_status_name}</Badge>
          {isRequirementOverdue(row.original.target_fill_date, row.original.req_status_code) && <OverdueBadge />}
        </div>
      ),
    },
    {
      accessorKey: "created_on",
      header: "Created",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.created_on ? fmtDate(row.original.created_on) : "—"}</span>,
    },
  ];

  // A single contextual (⋮) menu for HM/Admin — no standalone buttons. The page
  // decides visibility (recruiters get no handlers → no menu) and which handlers
  // to pass (onAssign only for admins).
  const hasMenu = opts && (opts.onView || opts.onEdit || opts.onAssign || opts.onSetStatus || opts.onEndRecruitment || opts.onExtendDate);
  if (hasMenu) {
    columns.push({
      id: "actions",
      header: "",
      enableSorting: false,
      enableHiding: false,
      cell: ({ row }) => {
        const r = row.original;
        // Read-only role (Recruiter): a plain Eye button, no ⋮ menu.
        const onlyView = opts.onView && !opts.onEdit && !opts.onAssign && !opts.onSetStatus;
        if (onlyView) {
          return (
            <div className="text-right" onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="sm" aria-label="View requirement" onClick={() => opts.onView?.(r)}>
                <Eye className="h-4 w-4" />
              </Button>
            </div>
          );
        }
        const terminal = TERMINAL_STATUS_CODES.has(r.req_status_code);
        // A permanently ended requirement is final — treat it like a terminal
        // state: no edit, no lifecycle changes, no extend, no reversal (View only).
        const frozen = terminal || r.recruitment_ended;
        const statusActions =
          opts.onSetStatus && !r.recruitment_ended ? manualStatusActions(r.req_status_code) : [];
        // End Recruitment: HM-only, for an EXPIRED + Partially Filled requirement
        // that hasn't already ended. Permanently withdraws the remaining seats and
        // closes the remaining applications.
        const canEndRecruitment =
          !!opts.onEndRecruitment &&
          r.req_status_code === "PARTIAL_FILLED" &&
          !!r.is_expired &&
          !r.recruitment_ended;
        // Extend Target Fill Date: HM-only, offered while Expired (restores
        // recruitment). Never for a permanently ended requirement.
        const canExtendDate = !!opts.onExtendDate && !!r.is_expired && !r.recruitment_ended;
        const canEdit = opts.onEdit && !frozen;
        const showFirstGroup = opts.onView || canEdit || canExtendDate;
        return (
          <div className="text-right" onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" aria-label="Requirement actions">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {opts.onView && (
                  <DropdownMenuItem onSelect={() => opts.onView?.(r)}>
                    <Eye className="h-4 w-4" /> View
                  </DropdownMenuItem>
                )}
                {canEdit && (
                  <DropdownMenuItem onSelect={() => opts.onEdit?.(r)}>
                    <Pencil className="h-4 w-4" /> Edit
                  </DropdownMenuItem>
                )}
                {canExtendDate && (
                  <DropdownMenuItem onSelect={() => opts.onExtendDate?.(r)}>
                    <CalendarClock className="h-4 w-4" /> Extend target fill date
                  </DropdownMenuItem>
                )}
                {statusActions.length > 0 && (
                  <>
                    {showFirstGroup && <DropdownMenuSeparator />}
                    {statusActions.map((a) => (
                      <DropdownMenuItem
                        key={a.to + a.label}
                        onSelect={() => opts.onSetStatus?.(r, a.to)}
                        className={a.danger ? "text-destructive focus:text-destructive" : undefined}
                      >
                        {a.label}
                      </DropdownMenuItem>
                    ))}
                  </>
                )}
                {canEndRecruitment && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onSelect={() => opts.onEndRecruitment?.(r)}
                      className="text-destructive focus:text-destructive"
                    >
                      <Ban className="h-4 w-4" /> End recruitment
                    </DropdownMenuItem>
                  </>
                )}
                {opts.onAssign && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={() => opts.onAssign?.(r)}>
                      <UserPlus className="h-4 w-4" /> {r.recruiter ? "Reassign recruiter" : "Assign recruiter"}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    });
  }

  return columns;
}
