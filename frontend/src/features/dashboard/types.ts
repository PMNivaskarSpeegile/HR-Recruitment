export interface Kpi {
  key: string;
  label: string;
  value: number;
  hint?: string;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface RecruiterWorkload {
  recruiter: string;
  requirements: number;
  candidates: number;
}

export interface RecentRequirement {
  req_tracker_no: string;
  jd_role_name: string;
  client_name: string | null;
  recruiter_name?: string | null;
  status: string | null;
  req_date: string | null;
  positions_required?: number;
  positions_filled?: number;
  positions_open?: number;
}

export interface TopClient {
  client_name: string;
  requirements: number;
  open_positions: number;
}

export interface StalledRequirement {
  req_tracker_no: string;
  jd_role_name: string;
  client_name: string | null;
  recruiter_name: string | null;
  status: string | null;
  open_positions: number;
  idle_days: number;
}

export type ActivityType =
  | "requirement_created"
  | "requirement_assigned"
  | "requirement_closed"
  | "candidate_added"
  | "candidate_joined";

export interface ActivityItem {
  type: ActivityType;
  title: string;
  ref?: string | null;
  when: string | null;
}

export interface AdminTask {
  key: string;
  label: string;
  count: number;
}

export interface RecentCandidate {
  cv_serial: string;
  candidate_name: string;
  status: string | null;
  created_on: string | null;
}

export interface UpcomingScreening {
  candidate_name: string;
  req_tracker_no: string;
  screening_datetime: string | null;
  status: string | null;
}

export interface DashboardData {
  role: "ADM" | "HM" | "REC";
  kpis: Kpi[];
  requirement_status?: StatusCount[];
  pipeline_status?: StatusCount[];
  pipeline_stages?: StatusCount[];
  recruiter_workload?: RecruiterWorkload[];
  recent_requirements?: RecentRequirement[];
  recent_candidates?: RecentCandidate[];
  upcoming_screenings?: UpcomingScreening[];
  // Admin-only sections
  top_clients?: TopClient[];
  admin_tasks?: AdminTask[];
  stalled_requirements?: StalledRequirement[];
  recent_activity?: ActivityItem[];
}
