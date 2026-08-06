// Maps an ATS status name to a Badge variant (see docs/DESIGN_SYSTEM.md §10).
export type StatusVariant =
  | "default"
  | "secondary"
  | "success"
  | "warning"
  | "danger"
  | "teal"
  | "muted"
  | "outline"
  | "blue"
  | "purple"
  | "orange"
  | "neutral";

const STATUS_VARIANT: Record<string, StatusVariant> = {
  // requirement lifecycle
  New: "muted",
  Assigned: "default",
  Open: "teal",
  Hold: "warning",
  "Partial Filled": "default",
  "Partially Filled": "default",
  "Close Filled": "success",
  Filled: "success",
  "Close Lost": "danger",
  "Closed Lost": "danger",
  Cancelled: "danger",
  // candidate global status — keep in lock-step with CANDIDATE_STATUS_VARIANT
  // (by code) so name-based badges (dashboard) match the Candidates page.
  "New CV": "blue",
  "Talent Pool": "purple",
  Saved: "purple",
  "Reject Hold": "orange",
  Joined: "success",
  Blacklisted: "neutral",
  // cv / pipeline
  Shortlisted: "default",
  "JD Email Sent": "teal",
  "Schedule Screening": "warning",
  "Screening Scheduled": "default",
  "OK to Proceed": "success",
  "Offer Released": "teal",
  "Awaiting Joining": "default",
  "Offer Accepted": "success",
  "Offer Declined": "danger",
  Withdrawn: "muted",
  Rejected: "danger",
  Fake: "danger",
  "Not Suitable": "muted",
  "Not Relevant": "muted",
  Dropped: "muted",
  "No Response": "warning",
  "Possible Duplicate": "orange",
  // System requirement-closure outcomes (auto-closed applications).
  "Requirement Filled": "muted",
  "Positions Withdrawn": "muted",
  "Requirement Closed Lost": "muted",
};

export function statusVariant(status?: string | null): StatusVariant {
  return (status && STATUS_VARIANT[status]) || "muted";
}

// Candidate profile-status display labels keyed by code. The SAVED status is
// presented as "Talent Pool" in the UI while its code stays SAVED.
const CANDIDATE_STATUS_LABEL: Record<string, string> = {
  SAVED: "Talent Pool",
};

/** UI label for a candidate profile status (falls back to the API status name). */
export function candidateStatusLabel(code?: string | null, name?: string | null): string {
  return (code && CANDIDATE_STATUS_LABEL[code]) || name || "";
}

// Candidate profile status → badge colour. Keyed by CODE (stable) so the colour
// is identical everywhere a candidate-status badge is shown. UI-only mapping.
const CANDIDATE_STATUS_VARIANT: Record<string, StatusVariant> = {
  NEW_CV: "blue",
  SAVED: "purple", // Talent Pool
  REJECT_HOLD: "orange", // system: 6-month cool-off
  JOINED: "success", // system: placed
  POSSIBLE_DUPLICATE: "orange",
  FAKE: "danger", // red
  BLACKLISTED: "neutral", // dark gray / black
};

/** Badge variant (colour) for a candidate profile status, by status code. */
export function candidateStatusVariant(code?: string | null): StatusVariant {
  return (code && CANDIDATE_STATUS_VARIANT[code]) || "muted";
}

// Position (seat) status → badge colour, by code.
const POSITION_STATUS_VARIANT: Record<string, StatusVariant> = {
  OPEN: "teal",
  HOLD: "warning",
  FILLED: "success",
  CANCELLED: "danger",
  INACTIVE: "muted", // system-managed (requirement Hold/Cancel)
  IN_PROGRESS: "default",
};

/** Badge variant for a position status, by status code. */
export function positionStatusVariant(code?: string | null): StatusVariant {
  return (code && POSITION_STATUS_VARIANT[code]) || "muted";
}

// Manual position actions a Hiring Manager may take, by current status.
// Filled is terminal (no actions). Mirrors the backend state machine.
export function positionStatusActions(code?: string | null): { label: string; to: string; danger?: boolean }[] {
  switch (code) {
    case "OPEN":
      return [{ label: "Put on Hold", to: "HOLD" }, { label: "Cancel Position", to: "CANCELLED", danger: true }];
    case "HOLD":
      return [{ label: "Resume (Open)", to: "OPEN" }, { label: "Cancel Position", to: "CANCELLED", danger: true }];
    case "CANCELLED":
      return [{ label: "Reopen Position", to: "OPEN" }];
    default:
      return []; // FILLED (terminal) and anything else → no manual actions
  }
}

// Statuses a recruiter may set manually (Talent Pool / Fake / Blacklisted).
// NEW CV + Possible Duplicate are system-assigned and intentionally absent.
// Only Fake / Blacklisted are manually settable. Talent Pool (SAVED), Reject
// Hold and Joined are system-managed by the candidate-lifecycle automation.
export const MANUAL_CANDIDATE_STATUSES: { code: string; label: string }[] = [
  { code: "FAKE", label: "Fake" },
  { code: "BLACKLISTED", label: "Blacklisted" },
];
