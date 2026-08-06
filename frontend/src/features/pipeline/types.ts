export interface Mapping {
  mapping_id: number;
  req: number;
  req_tracker_no: string;
  recruiter_name: string | null;
  candidate: number;
  cv_serial: string;
  candidate_name: string;
  mobile: string;
  email: string;
  // Stage and Outcome are independent: stage = current position; latest_outcome
  // = last recorded disposition; is_closed = terminal.
  application_stage_name: string | null;
  application_stage_code: string | null;
  latest_outcome_name: string | null;
  latest_outcome_code: string | null;
  is_closed: boolean;
  closed_on: string | null;
  screening_datetime: string | null;
  screening_mode_name: string | null;
  comments: string | null;
  created_on: string | null;
  updated_on: string | null;
}

export interface TimelineEvent {
  type: string;
  title: string;
  detail: string | null;
  actor: string | null;
  timestamp: string | null;
}
