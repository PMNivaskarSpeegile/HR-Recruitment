// Chart palette — design-system tokens + the documented chart status palette.
// (See docs/DESIGN_SYSTEM.md §1 + §12. No raw hex in components — import from here.)
export const CHART = {
  primary: "#2563EB",
  teal: "#14B8A6",
  success: "#16A34A",
  warning: "#F59E0B",
  danger: "#DC2626",
  muted: "#94A3B8",
  grid: "#E2E8F0",
  axis: "#475569",
  label: "#334155",
} as const;

const FALLBACK = "#94A3B8";

/**
 * Semantic status → colour map, keyed by the status *display names* the API
 * returns (application_stage / req_status `status_name`). Each pipeline/requirement
 * stage gets a distinct, meaningful hue so bars and donut slices are readable
 * without relying on order. Future stages (offer/joined) are mapped ahead of
 * time so they slot in automatically if the workflow ever extends.
 */
export const STATUS_COLOR: Record<string, string> = {
  // ---- Requirement lifecycle ----
  New: "#94A3B8", // slate
  Open: "#2563EB", // blue (primary)
  Assigned: "#4F46E5", // indigo
  Hold: "#F59E0B", // orange
  "Partial Filled": "#14B8A6", // teal
  "Close Filled": "#16A34A", // green
  "Close Lost": "#B91C1C", // dark red
  Cancelled: "#DC2626", // red
  Expired: "#64748B", // slate gray

  // ---- Candidate pipeline ----
  "New CV": "#94A3B8", // gray
  Saved: "#64748B", // slate
  Shortlisted: "#7C3AED", // purple
  "JD Email Sent": "#14B8A6", // teal
  "Schedule Screening": "#F59E0B", // orange
  "Screening Scheduled": "#06B6D4", // cyan
  "OK to Proceed": "#16A34A", // green
  "No Response": "#94A3B8", // gray
  Rejected: "#DC2626", // red
  "Not Suitable": "#991B1B", // dark red
  Fake: "#92400E", // brown
  Dropped: "#64748B", // slate gray
  "Possible Duplicate": "#F59E0B", // amber

  // ---- Future workflow stages (not modelled yet) ----
  "Interview Scheduled": "#06B6D4", // cyan
  "Interview Completed": "#2563EB", // blue
  "Offer Released": "#10B981", // emerald
  Joined: "#065F46", // dark green
};

/** Resolve a status display-name to its semantic chart colour. */
export function statusColor(status?: string | null): string {
  return (status && STATUS_COLOR[status]) || FALLBACK;
}
