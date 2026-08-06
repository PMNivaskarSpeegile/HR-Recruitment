import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Paginated, Requirement } from "./types";

/** Default page size for server-paginated requirement lists & pickers. */
export const REQUIREMENTS_PAGE_SIZE = 20;

export interface RequirementListParams {
  page?: number;
  pageSize?: number;
  search?: string;
  /** "active" (non-terminal), a specific req_status_code, or null. */
  status?: string | null;
  /** "recruiter" | "hm" — requirements missing that assignment. */
  missing?: string | null;
  ordering?: string;
  enabled?: boolean;
}

/**
 * Server-paginated + searched + filtered requirement list (role-scoped on the
 * backend). Every filter is applied server-side so counts match the dashboard
 * and no record is hidden behind a client-side 100-row cap. `keepPreviousData`
 * keeps the current page visible while the next loads.
 */
export function useRequirements(params: RequirementListParams = {}) {
  const {
    page = 1,
    pageSize = REQUIREMENTS_PAGE_SIZE,
    search = "",
    status = null,
    missing = null,
    ordering = "-req_id",
    enabled = true,
  } = params;
  return useQuery({
    queryKey: ["requirements", { page, pageSize, search, status, missing, ordering }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (await api.get<Paginated<Requirement>>("/requirements/", {
        params: {
          page,
          page_size: pageSize,
          ordering,
          search: search || undefined,
          status: status || undefined,
          missing: missing || undefined,
        },
      })).data,
  });
}

/** Single requirement (role-scoped on the backend → 404 if not visible to the user). */
export function useRequirement(id: string | number | null) {
  return useQuery({
    queryKey: ["requirement", String(id)],
    enabled: id != null,
    queryFn: async () => (await api.get<Requirement>(`/requirements/${id}/`)).data,
  });
}

export function useCreateRequirement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => (await api.post("/requirements/", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateRequirement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, payload }: { reqId: number; payload: Record<string, unknown> }) =>
      (await api.patch(`/requirements/${reqId}/`, payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useAssignRequirement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, recruiter }: { reqId: number; recruiter: number }) =>
      (await api.post(`/requirements/${reqId}/assign/`, { recruiter })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Manual requirement status change (HM/Admin): Hold / Resume / Cancel. */
export function useSetRequirementStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, toStatus, reason }: { reqId: number; toStatus: string; reason?: string }) =>
      (await api.post(`/requirements/${reqId}/set-status/`, { to_status: toStatus, reason })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["status-history"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** End recruitment on an expired, partially-filled requirement (HM only):
 *  closes the remaining active applications and frees those candidates to the
 *  Talent Pool; the requirement stays Partial Filled + Expired. */
export function useEndRecruitment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, reason }: { reqId: number; reason?: string }) =>
      (await api.post(`/requirements/${reqId}/end-recruitment/`, { reason })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["status-history"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// --- Positions (seats) — tracked independently under the requirement --------- #
export interface Position {
  position_id: number;
  req: number;
  position_no: number;
  position_status: number | null;
  position_status_code: string | null;
  position_status_name: string | null;
  status_source: string | null;
  auto_inactive: boolean;
  filled_by_mapping: number | null;
  filled_by_candidate: string | null;
  is_active: boolean;
  created_on: string | null;
  updated_on: string | null;
}

export function usePositions(reqId: string | number | null) {
  return useQuery({
    queryKey: ["positions", String(reqId)],
    enabled: reqId != null,
    queryFn: async () => (await api.get<Position[]>(`/requirements/${reqId}/positions/`)).data,
  });
}

export function useSetPositionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, positionId, toStatus, reason }: { reqId: number; positionId: number; toStatus: string; reason?: string }) =>
      (await api.post(`/requirements/${reqId}/set-position-status/`, {
        position_id: positionId,
        to_status: toStatus,
        reason,
      })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["status-history"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** HM/Admin: add N new Open seats to an active requirement. */
export function useAddPositions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, count }: { reqId: number; count: number }) =>
      (await api.post(`/requirements/${reqId}/add-positions/`, { count })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** HM/Admin: delete a never-filled seat (guarded server-side). */
export function useDeletePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, positionId }: { reqId: number; positionId: number }) =>
      (await api.post(`/requirements/${reqId}/delete-position/`, { position_id: positionId })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["requirements"] });
      qc.invalidateQueries({ queryKey: ["requirement"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export interface StatusHistoryRow {
  history_id: number;
  entity_type: "REQUIREMENT" | "POSITION";
  entity_id: number;
  previous_status: string | null;
  new_status: string;
  reason: string | null;
  change_type: "MANUAL" | "AUTO";
  changed_by_name: string | null;
  changed_on: string | null;
}

/** Combined requirement + position status audit timeline. */
export function useRequirementStatusHistory(reqId: string | number | null) {
  return useQuery({
    queryKey: ["status-history", String(reqId)],
    enabled: reqId != null,
    queryFn: async () =>
      (await api.get<StatusHistoryRow[]>(`/requirements/${reqId}/status-history/`)).data,
  });
}
