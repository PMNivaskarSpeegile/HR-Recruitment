export interface Candidate {
  cv_id: number;
  cv_serial: string;
  candidate_name: string;
  mobile: string;
  email: string;
  exp_min: string | null;
  exp_max: string | null;
  candidate_status_name: string | null;
  candidate_status_code: string | null;
  current_location_name: string | null;
  notice_period_name: string | null;
  work_mode_name: string | null;
  source_name: string | null;
  uploaded_by_name: string | null;
  skill_names: string[];
  skill_ids?: number[];
  is_willing_to_relocate: boolean;
  created_on: string | null;
  // Editable master-profile fields (verify & update) + FK ids for prefill.
  current_company?: string | null;
  current_designation?: string | null;
  highest_qualification?: string | null;
  certifications?: string | null;
  additional_notes?: string | null;
  relevant_exp?: string | null;
  current_ctc_lpa?: string | null;
  expected_ctc_lpa?: string | null;
  current_location?: number | null;
  notice_period?: number | null;
  work_mode?: number | null;
  source?: number | null;
  // Bulk-import preservation fields (age_at_import is a snapshot — never recalculated).
  date_of_birth?: string | null;
  age_at_import?: number | null;
  postal_address?: string | null;
  current_location_text?: string | null;
  // Verification stamp.
  profile_verified?: boolean;
  profile_verified_by_name?: string | null;
  profile_verified_on?: string | null;
  // Present only in the requirement review pool (skill-match score).
  matched_skills?: number;
  required_skills?: number;
  skill_match_pct?: number;
}

export interface RequirementHistoryItem {
  mapping_id: number;
  req_id: number;
  req_tracker_no: string;
  jd_role_name: string;
  client_name: string | null;
  recruiter_name: string | null;
  status: string | null;
  status_code: string | null;
  created_on: string | null;
}

export interface TimelineEvent {
  type: string;
  title: string;
  detail: string | null;
  actor: string | null;
  timestamp: string | null;
  // Requirement an application event belongs to (null for candidate-level events
  // such as creation/import), so the global feed can tag each event in context.
  req_id: number | null;
  req_tracker_no: string | null;
  req_role: string | null;
}

export interface ResumeInfo {
  document_id: number;
  file_name: string;
  file_type: string | null;
  file_size: number | null;
  uploaded_on: string | null;
  available: boolean;
}

export interface ActiveReview {
  review_id: number;
  req_id: number;
  req_tracker_no: string;
  jd_role_name: string;
  client_name: string | null;
  tagged_on: string | null;
}

export interface CandidateDetail {
  candidate: Candidate;
  resume: ResumeInfo | null;
  requirement_history: RequirementHistoryItem[];
  active_reviews: ActiveReview[];
  timeline: TimelineEvent[];
}
