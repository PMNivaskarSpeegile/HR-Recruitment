/**
 * Single source of truth for workflow ACTION labels (buttons / menu items).
 *
 * Terminology rule (kept consistent across Pipeline, Screening popup, Verify &
 * Update, and the Candidate Drawer):
 *   - ACTIONS (buttons / menu items) use VERBS — e.g. Shortlist, Send JD,
 *     Schedule Screening, Reschedule, Reject, Drop, Blacklist, Mark Fake,
 *     Release Offer, Withdraw, Mark Joined.
 *   - STATUSES / OUTCOMES (stage tabs, badges, latest status, activity timeline,
 *     communication list) use STATE labels — these come from the backend
 *     `status_name` (Shortlisted, Rejected, Dropped, Blacklisted, …) via
 *     `statusVariant` / the API, so they are already consistent. Do NOT hardcode
 *     state labels in the UI; render the API name.
 *
 * Keys are the codes used as menu items — both board transition codes
 * (mappingColumns `onTransition`) and engine outcome codes (screening popup).
 */
export const ACTION_LABEL: Record<string, string> = {
  // pure workflow actions
  SEND_JD: "Send JD",
  SCHEDULE_SCREENING: "Schedule Screening",
  RESCHEDULE: "Reschedule",
  RELEASE_OFFER: "Release Offer",
  SHORTLIST: "Shortlist",
  // advancing outcome (screening pass → OK to Proceed stage)
  PASSED: "OK to Proceed",
  OK_TO_PROCEED: "OK to Proceed",
  // closing / recorded outcomes (verbs where one exists)
  REJECTED: "Reject",
  DROPPED: "Drop",
  FAKE: "Mark Fake",
  BLACKLISTED: "Blacklist",
  NO_RESPONSE: "No Response",
  // offer stage
  OFFERED: "Release Offer",
  OFFER_ACCEPTED: "Offer Accepted",
  AWAITING_JOINING: "Offer Accepted",
  OFFER_DECLINED: "Offer Declined",
  // awaiting joining
  JOINED: "Mark Joined",
  WITHDRAWN: "Withdraw",
};

/** Verb label for a workflow action/menu item, by code. */
export const actionLabel = (code: string): string => ACTION_LABEL[code] ?? code;
