export interface Requirement {
  req_id: number;
  req_tracker_no: string;
  jd_serial_number: string | null;
  client_req_id: string | null;
  jd_role_name: string;
  client_name: string;
  req_type_name: string;
  req_status_name: string;
  req_status_code: string;
  priority_name: string | null;
  location_name: string | null;
  recruiter: number | null;
  recruiter_name: string | null;
  hiring_mgr_name: string | null;
  positions_open: number;
  positions_filled: number;
  skill_names: string[];
  req_date: string;              // system creation date (not user-editable)
  created_on: string | null;     // system creation timestamp → shown as "Created"
  assigned_date: string | null;
  target_fill_date: string | null;  // user "Required by" deadline → shown as "Target close"

  // Foreign-key ids + raw fields (returned by the read serializer) — used to
  // prefill the Edit form and the read-only View.
  client: number | null;
  client_mgr: number | null;
  req_type: number | null;
  location: number | null;
  np: number | null;
  priority: number | null;
  skill1: number | null;
  skill2: number | null;
  skill3: number | null;
  exp_min: string | null;
  exp_max: string | null;
  jd_rate_lpa: string | null;
  jd_text: string | null;

  // Derived Expired overlay (never a stored status) + per-seat breakdown.
  is_expired: boolean;
  expired_on: string | null;
  position_counts: {
    total: number;
    open: number;
    filled: number;
    held: number;
    cancelled: number;
    inactive: number;
  };
  // Permanent End-Recruitment business decision (persisted on the requirement).
  recruitment_ended: boolean;
  recruitment_ended_on: string | null;
  recruitment_ended_by: number | null;
  recruitment_ended_by_name: string | null;
  // Open (active, not-closed) applications — shown in the End-Recruitment summary.
  active_application_count: number;
}

export type { Paginated } from "@/lib/types";
