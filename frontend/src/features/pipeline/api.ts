import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Paginated } from "@/lib/types";
import type { Candidate } from "@/features/candidates/types";
import type { Mapping } from "./types";

/** Server page size for the requirement review pool. */
export const NEW_CV_PAGE_SIZE = 20;

/** Usable candidates for a requirement (not yet mapped), ranked by skill match.
 *  Server-side paginated + searched so it scales as the repository grows; the
 *  server computes matched_skills and orders by relevance before paging. */
export function useNewCvs(reqId: string | null, page = 1, search = "") {
  return useQuery({
    queryKey: ["new-cvs", reqId, page, search],
    enabled: !!reqId,
    placeholderData: keepPreviousData, // keep the current page visible while the next loads
    queryFn: async () =>
      (
        await api.get<Paginated<Candidate>>("/pipeline/new-cvs/", {
          params: { requirement: reqId, page, page_size: NEW_CV_PAGE_SIZE, search: search || undefined },
        })
      ).data,
  });
}

export interface ReviewInput {
  requirement: number;
  candidate: number;
  // Initial resume review verdict only.
  decision: "SHORTLISTED" | "NOT_SUITABLE";
  rejection_reason?: number;
  comments?: string;
}

export function useReviewCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ReviewInput) => (await api.post("/pipeline/review/", body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["new-cvs"] });
      qc.invalidateQueries({ queryKey: ["mappings"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      // Refresh the candidate drawer's requirement history live (tag-to-requirement).
      qc.invalidateQueries({ queryKey: ["candidate-detail"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Pipeline mappings for a requirement, filtered by stage (UC4/UC5). */
export function useMappings(reqId: string | null, status: string) {
  return useQuery({
    queryKey: ["mappings", reqId, status],
    enabled: !!reqId,
    queryFn: async () =>
      (await api.get<Paginated<Mapping>>("/pipeline/mappings/", { params: { requirement: reqId, status } })).data,
  });
}

function invalidatePipeline(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["mappings"] });
  qc.invalidateQueries({ queryKey: ["new-cvs"] });
  qc.invalidateQueries({ queryKey: ["dashboard"] });
  // A Join fills a seat + rolls up the requirement status.
  qc.invalidateQueries({ queryKey: ["positions"] });
  qc.invalidateQueries({ queryKey: ["requirements"] });
}

export interface JdPreviewRecipient {
  mapping_id: number;
  candidate_name: string;
  recipient: string;
  subject: string;
  body: string;
}

export interface JdPreview {
  template_id: number;
  template_code: string;
  subject_template: string;
  body_template: string;
  recipients: JdPreviewRecipient[];
}

/** Render (without sending) the JD email per shortlisted recipient (UC4). */
export function useJdPreview() {
  return useMutation({
    mutationFn: async (body: { requirement: number; mapping_ids: number[] }) =>
      (await api.post<JdPreview>("/pipeline/jd-preview/", body)).data,
  });
}

export function useSendJd() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { requirement: number; mapping_ids: number[] }) =>
      (await api.post("/pipeline/send-jd/", body)).data,
    onSuccess: () => {
      invalidatePipeline(qc);
      qc.invalidateQueries({ queryKey: ["communications"] });
    },
  });
}

export interface Communication {
  comm_id: number;
  candidate: number;
  candidate_name: string;
  channel: string;
  recipient: string;
  subject: string | null;
  body: string | null;
  status: string;
  error_message: string | null;
  sent_by: number | null;
  sent_by_name: string | null;
  sent_on: string | null;
}

/** JD email tracker — every send attempt for a requirement, newest first (UC4). */
export function useCommunications(reqId: string | null) {
  return useQuery({
    queryKey: ["communications", reqId],
    enabled: !!reqId,
    queryFn: async () =>
      (await api.get<Paginated<Communication>>("/pipeline/communications/", { params: { requirement: reqId } })).data,
  });
}

export interface TransitionInput {
  requirement: number;
  mapping_ids: number[];
  to_status: string;
  comments?: string;
  screening_datetime?: string;
  screening_mode?: number;
  rejection_reason?: number;
}

export function useTransition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TransitionInput) => (await api.post("/pipeline/transition/", body)).data,
    onSuccess: () => invalidatePipeline(qc),
  });
}

// --- Centralized Stage × Outcome engine ------------------------------------ #
/** Record a stage OUTCOME (advance or close). `move_to_talent_pool` answers the
 *  "Move candidate to Talent Pool?" prompt on a non-hired close. */
export function useRecordOutcome() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      mapping: number; outcome: string; reason?: string;
      rejection_reason?: number; move_to_talent_pool?: boolean;
    }) => (await api.post<Mapping>("/pipeline/outcome/", body)).data,
    onSuccess: () => {
      invalidatePipeline(qc);
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["mapping-timeline"] });
    },
  });
}

/** Advance a stage via an action (Send JD / Schedule Screening / Release Offer). */
export function useAdvanceStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      mapping: number; action: "SEND_JD" | "SCHEDULE_SCREENING" | "RELEASE_OFFER";
      screening_datetime?: string; screening_mode?: number; reason?: string;
    }) => (await api.post<Mapping>("/pipeline/advance/", body)).data,
    onSuccess: () => {
      invalidatePipeline(qc);
      qc.invalidateQueries({ queryKey: ["mapping-timeline"] });
    },
  });
}

/** Reschedule a scheduled screening (server enforces a future date/time). */
export function useRescheduleScreening() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { mapping: number; scheduled_at: string; screening_mode?: number }) =>
      (await api.post<Mapping>("/pipeline/reschedule/", body)).data,
    onSuccess: () => {
      invalidatePipeline(qc);
      qc.invalidateQueries({ queryKey: ["mapping-timeline"] });
    },
  });
}

/** The per-requirement recruitment timeline for one application. */
export function useMappingTimeline(mappingId: number | null) {
  return useQuery({
    queryKey: ["mapping-timeline", mappingId],
    enabled: mappingId != null,
    queryFn: async () =>
      (await api.get<{ mapping: Mapping; timeline: import("./types").TimelineEvent[] }>(
        `/pipeline/mappings/${mappingId}/timeline/`,
      )).data,
  });
}

// --- Screening rounds (sequential screening workflow) ----------------------- #
export interface Screening {
  screening_id: number;
  mapping: number;
  screening_mode: number;
  screening_mode_name: string;
  screening_mode_code: string;
  status: "SCHEDULED" | "COMPLETED";
  outcome: string | null;
  scheduled_at: string | null;
  interviewer: string | null;
  notes: string | null;
  created_by_name: string | null;
  created_on: string | null;
}

export function useScreenings(mappingId: number | null) {
  return useQuery({
    queryKey: ["screenings", mappingId],
    enabled: mappingId != null,
    queryFn: async () =>
      (await api.get<Screening[]>("/pipeline/screenings/", { params: { mapping: mappingId } })).data,
  });
}

export function useScheduleScreening() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      mapping: number;
      screening_mode: number;
      scheduled_at: string;
      interviewer?: string;
      notes?: string;
    }) => (await api.post<Screening>("/pipeline/screenings/", body)).data,
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["screenings", s.mapping] });
      invalidatePipeline(qc);
    },
  });
}

export function useCompleteScreening() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, outcome, notes }: { id: number; outcome: string; notes?: string }) =>
      (await api.post<Screening>(`/pipeline/screenings/${id}/complete/`, { outcome, notes })).data,
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["screenings", s.mapping] });
      invalidatePipeline(qc);
    },
  });
}

export function useRescheduleScreeningRound() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, scheduled_at }: { id: number; scheduled_at: string }) =>
      (await api.post<Screening>(`/pipeline/screenings/${id}/reschedule/`, { scheduled_at })).data,
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["screenings", s.mapping] });
      invalidatePipeline(qc);
    },
  });
}
