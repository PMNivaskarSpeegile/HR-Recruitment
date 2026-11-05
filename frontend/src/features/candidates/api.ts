// import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import { api } from "@/api/client";
// import type { Paginated } from "@/lib/types";
// import type { Candidate, CandidateDetail } from "./types";

// /** Default page size for the server-paginated candidate list. */
// export const CANDIDATES_PAGE_SIZE = 20;

// /** Composite Candidate Details payload for the drawer (read-only). */
// export function useCandidateDetail(id: number | null) {
//   return useQuery({
//     queryKey: ["candidate-detail", id],
//     enabled: id != null,
//     queryFn: async () => (await api.get<CandidateDetail>(`/candidates/${id}/detail/`)).data,
//   });
// }

// /** Fetch the résumé as an authed blob and return an object URL (caller revokes). */
// export async function fetchCandidateResume(id: number): Promise<string> {
//   const res = await api.get(`/candidates/${id}/resume/`, { responseType: "blob" });
//   return URL.createObjectURL(res.data as Blob);
// }

// export function useCandidates(
//   status?: string,
//   requirement?: string,
//   page = 1,
//   search = "",
//   skillIds: number[] = [],
// ) {
//   // `status`: a candidate_status code, or "ALL" to override the default view.
//   // Omitted → backend's default Candidate Database (hides Reject-Hold/Joined/
//   // Fake/Blacklisted for REC/ADM; HM is always restricted server-side).
//   // `requirement`: scope to candidates mapped to that requirement.
//   // `skillIds`: candidates having ALL the given skills (server-side AND filter).
//   // Server-paginated + searched (name/mobile/email/company/location) so the list
//   // scales past the old 100-row client cap. `keepPreviousData` avoids a flash
//   // between pages.
//   return useQuery({
//     queryKey: ["candidates", status ?? "default", requirement ?? "all", page, search, skillIds],
//     placeholderData: keepPreviousData,
//     queryFn: async () =>
//       (await api.get<Paginated<Candidate>>("/candidates/", {
//         // `indexes: null` serialises skill[] as repeated `skill=1&skill=2`
//         // (what Django's getlist("skill") reads), not `skill[]=1`.
//         paramsSerializer: { indexes: null },
//         params: {
//           page,
//           page_size: CANDIDATES_PAGE_SIZE,
//           ordering: "-cv_id",
//           search: search || undefined,
//           ...(status ? { status } : {}),
//           ...(requirement ? { requirement } : {}),
//           ...(skillIds.length ? { skill: skillIds } : {}),
//         },
//       })).data,
//   });
// }

// export function useCreateCandidate() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async (payload: Record<string, unknown>) => (await api.post("/candidates/", payload)).data,
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["candidates"] });
//       qc.invalidateQueries({ queryKey: ["dashboard"] });
//     },
//   });
// }

// function _invalidateCandidate(qc: ReturnType<typeof useQueryClient>, id: number) {
//   qc.invalidateQueries({ queryKey: ["candidate-detail", id] });
//   qc.invalidateQueries({ queryKey: ["candidates"] });
//   qc.invalidateQueries({ queryKey: ["dashboard"] });
// }

// /** Mark a candidate Fake / Blacklisted (mandatory reason). Mutually exclusive. */
// export function useSetCandidateStatus() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, status_code, reason }: { id: number; status_code: string; reason: string }) =>
//       (await api.post(`/candidates/${id}/set-status/`, { status_code, reason })).data,
//     onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
//   });
// }

// /** Verify & update the MASTER candidate profile (recruiter/admin). */
// export function useVerifyCandidateProfile() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, ...payload }: { id: number } & Record<string, unknown>) =>
//       (await api.post(`/candidates/${id}/verify-profile/`, payload)).data,
//     onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
//   });
// }

// /** Add a candidate to one or more requirements' Review Pools ("under review").
//  *  Explicit pre-pipeline tag — never creates a jd_cv_mapping. §9: only the
//  *  requirement's assigned recruiter (or an admin) may tag. */
// export function useTagRequirement() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, requirementIds }: { id: number; requirementIds: number[] }) =>
//       (await api.post(`/candidates/${id}/tag-requirements/`, { requirement_ids: requirementIds })).data,
//     onSuccess: (_data, vars) => {
//       _invalidateCandidate(qc, vars.id);
//       qc.invalidateQueries({ queryKey: ["new-cvs"] }); // review pool
//     },
//   });
// }

// /** Remove a candidate from a requirement's Review Pool. */
// export function useUntagRequirement() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, requirement }: { id: number; requirement: number }) =>
//       (await api.post(`/candidates/${id}/untag-requirement/`, { requirement })).data,
//     onSuccess: (_data, vars) => {
//       _invalidateCandidate(qc, vars.id);
//       qc.invalidateQueries({ queryKey: ["new-cvs"] });
//     },
//   });
// }

// /** Admin: remove a Fake / Blacklisted mark → restore the candidate to Talent Pool. */
// export function useClearCandidateStatus() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, reason }: { id: number; reason?: string }) =>
//       (await api.post(`/candidates/${id}/clear-status/`, { reason })).data,
//     onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
//   });
// }

// export type BulkRowStatus = "VALID" | "INVALID" | "DUPLICATE" | "UPDATE" | "CREATED" | "UPDATED" | "ERROR";

// export interface BulkRow {
//   excel_row: number;
//   name: string;
//   mobile: string;
//   email: string;
//   status: BulkRowStatus;
//   errors: string[];
//   warnings: string[];
//   duplicate?: { existing_cv_serial: string; existing_cv_id: number } | null;
// }

// export interface BulkSummary {
//   total: number;
//   valid: number;
//   update: number;
//   duplicate: number;
//   invalid: number;
//   warnings: number;
// }

// export interface DuplicateFileInfo {
//   batch_id: number;
//   file_name: string | null;
//   created_on: string | null;
// }

// export interface BulkPreview {
//   ok: boolean;
//   error?: string;
//   batch_id?: number | null;   // DRAFT batch to confirm at import (Feature 5a)
//   header_row?: number;
//   summary?: BulkSummary;
//   rows: BulkRow[];
//   duplicate_file?: DuplicateFileInfo | null;
// }

// export interface BulkImportReport {
//   ok: boolean;
//   error?: string;
//   created: number;
//   updated: number;
//   possible_duplicates: { row: number; mobile: string; existing_cv_serial: string }[];
//   skipped: { row: number; errors: string[] }[];
//   warnings: { row: number; messages: string[] }[];
//   rows: BulkRow[];
//   duplicate_file?: DuplicateFileInfo | null;
// }

// /** Validate-only preview — no DB writes. */
// export function useBulkPreview() {
//   return useMutation({
//     mutationFn: async ({ file }: { file: File }) => {
//       const form = new FormData();
//       form.append("file", file);
//       return (await api.post<BulkPreview>("/candidates/bulk-preview/", form)).data;
//     },
//   });
// }

// /** Import valid rows. Preferred: confirm a preview DRAFT via `batchId` (imports the
//  *  exact validated dataset). Fallback: a direct `file`. Optional requirement + source. */
// export function useBulkImport() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ batchId, file, requirement, source }:
//       { batchId?: number | null; file?: File; requirement?: string; source?: string }) => {
//       const form = new FormData();
//       if (batchId != null) form.append("batch_id", String(batchId));
//       else if (file) form.append("file", file);
//       if (requirement) form.append("requirement", requirement);
//       if (source) form.append("source", source);
//       return (await api.post<BulkImportReport>("/candidates/bulk-upload/", form)).data;
//     },
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["candidates"] });
//       qc.invalidateQueries({ queryKey: ["dashboard"] });
//       qc.invalidateQueries({ queryKey: ["import-batches"] });
//     },
//   });
// }

// // --- Duplicate Review workflow (separate from candidate status) --------------
// export interface DuplicateReview {
//   review_id: number;
//   existing_candidate: number;
//   existing_candidate_detail: {
//     cv_id: number;
//     cv_serial: string;
//     candidate_name: string;
//     mobile: string;
//     email: string;
//     current_company: string | null;
//     candidate_status_name: string | null;
//   } | null;
//   new_candidate_name: string;
//   new_mobile: string;
//   new_email: string | null;
//   detection_reason: string;
//   review_status: "PENDING" | "RESOLVED";
//   resolution: "MERGED" | "KEPT_SEPARATE" | "CORRECTED" | null;
//   notes: string | null;
//   created_by_name: string | null;
//   created_on: string | null;
//   resolved_by_name: string | null;
//   resolved_on: string | null;
// }

// /** Admin-only list of duplicate reviews (optionally filtered by status). */
// export function useDuplicateReviews(status?: "PENDING" | "RESOLVED") {
//   return useQuery({
//     queryKey: ["duplicate-reviews", status ?? "all"],
//     queryFn: async () =>
//       (await api.get<Paginated<DuplicateReview>>("/duplicate-reviews/", {
//         params: { page_size: 100, ...(status ? { review_status: status } : {}) },
//       })).data,
//   });
// }

// /** Recruiter/Admin: submit a detected duplicate for Admin review. */
// export function useCreateDuplicateReview() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async (payload: Record<string, unknown>) =>
//       (await api.post("/duplicate-reviews/", payload)).data,
//     onSuccess: () => qc.invalidateQueries({ queryKey: ["duplicate-reviews"] }),
//   });
// }

// /** Admin: resolve a review (merge/keep-separate/correct). */
// export function useResolveDuplicateReview() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id, ...body }: { id: number } & Record<string, unknown>) =>
//       (await api.post(`/duplicate-reviews/${id}/resolve/`, body)).data,
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["duplicate-reviews"] });
//       qc.invalidateQueries({ queryKey: ["candidates"] });
//     },
//   });
// }

// // --- Import batch history (Feature 2) ----------------------------------------
// export interface ImportBatch {
//   batch_id: number;
//   batch_uid: string | null;
//   uploaded_by_name: string | null;
//   file_name: string | null;
//   source_name: string | null;
//   requirement_tracker_no: string | null;
//   header_row: number | null;
//   total_rows: number;
//   created_count: number;
//   updated_count: number;
//   duplicate_count: number;
//   skipped_count: number;
//   status: "PENDING" | "COMPLETED" | "FAILED" | "ROLLED_BACK";
//   created_on: string | null;
//   completed_on: string | null;
// }

// /** Import history — own uploads for a recruiter, all for an admin. */
// export function useImportBatches() {
//   return useQuery({
//     queryKey: ["import-batches"],
//     queryFn: async () =>
//       (await api.get<Paginated<ImportBatch>>("/import-batches/", { params: { page_size: 100 } })).data,
//   });
// }

// /** Roll back a batch (soft-delete the untouched candidates it created). */
// export function useRollbackImportBatch() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ id }: { id: number }) =>
//       (await api.post<{ removed: string[]; kept: { cv_serial: string; reason: string }[]; removed_count: number; kept_count: number }>(
//         `/import-batches/${id}/rollback/`, {})).data,
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["import-batches"] });
//       qc.invalidateQueries({ queryKey: ["candidates"] });
//       qc.invalidateQueries({ queryKey: ["dashboard"] });
//     },
//   });
// }

// export async function downloadBatchReport(id: number) {
//   const res = await api.get(`/import-batches/${id}/report/`, { responseType: "blob" });
//   const url = URL.createObjectURL(res.data as Blob);
//   const a = document.createElement("a");
//   a.href = url;
//   a.download = `import_batch_${id}_report.xlsx`;
//   document.body.appendChild(a);
//   a.click();
//   a.remove();
//   URL.revokeObjectURL(url);
// }

// // --- Location reconciliation (Feature 3) -------------------------------------
// export interface UnmappedLocation {
//   text: string;
//   count: number;
//   suggested_location_id: number | null;
//   suggested_city: string | null;
// }

// /** Import "kept as text" locations still unmapped to Location Master. */
// export function useUnmappedLocations(enabled = true) {
//   return useQuery({
//     queryKey: ["unmapped-locations"],
//     enabled,
//     queryFn: async () => (await api.get<UnmappedLocation[]>("/candidates/unmapped-locations/")).data,
//   });
// }

// /** Map an unmapped location text to an existing Location Master city. */
// export function useReconcileLocation() {
//   const qc = useQueryClient();
//   return useMutation({
//     mutationFn: async ({ text, location_id }: { text: string; location_id: number }) =>
//       (await api.post<{ reconciled: number; location: string }>(
//         "/candidates/reconcile-location/", { text, location_id })).data,
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["unmapped-locations"] });
//       qc.invalidateQueries({ queryKey: ["candidates"] });
//     },
//   });
// }

// export async function downloadCandidateTemplate() {
//   const res = await api.get("/candidates/upload-template/", { responseType: "blob" });
//   const url = URL.createObjectURL(res.data as Blob);
//   const a = document.createElement("a");
//   a.href = url;
//   a.download = "candidate_upload_template.xlsx";
//   document.body.appendChild(a);
//   a.click();
//   a.remove();
//   URL.revokeObjectURL(url);
// }


import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Paginated } from "@/lib/types";
import type { Candidate, CandidateDetail } from "./types";

/** Default page size for the server-paginated candidate list. */
export const CANDIDATES_PAGE_SIZE = 20;

/** Composite Candidate Details payload for the drawer (read-only). */
export function useCandidateDetail(id: number | null) {
  return useQuery({
    queryKey: ["candidate-detail", id],
    enabled: id != null,
    queryFn: async () => (await api.get<CandidateDetail>(`/candidates/${id}/detail/`)).data,
  });
}

/** Fetch the résumé as an authed blob and return an object URL (caller revokes). */
export async function fetchCandidateResume(id: number): Promise<string> {
  const res = await api.get(`/candidates/${id}/resume/`, { responseType: "blob" });
  return URL.createObjectURL(res.data as Blob);
}

export function useCandidates(
  status?: string,
  requirement?: string,
  page = 1,
  search = "",
  skillIds: number[] = [],
) {
  // `status`: a candidate_status code, or "ALL" to override the default view.
  // Omitted → backend's default Candidate Database (hides Reject-Hold/Joined/
  // Fake/Blacklisted for REC/ADM; HM is always restricted server-side).
  // `requirement`: scope to candidates mapped to that requirement.
  // `skillIds`: candidates having ALL the given skills (server-side AND filter).
  // Server-paginated + searched (name/mobile/email/company/location) so the list
  // scales past the old 100-row client cap. `keepPreviousData` avoids a flash
  // between pages.
  return useQuery({
    queryKey: ["candidates", status ?? "default", requirement ?? "all", page, search, skillIds],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (await api.get<Paginated<Candidate>>("/candidates/", {
        // `indexes: null` serialises skill[] as repeated `skill=1&skill=2`
        // (what Django's getlist("skill") reads), not `skill[]=1`.
        paramsSerializer: { indexes: null },
        params: {
          page,
          page_size: CANDIDATES_PAGE_SIZE,
          ordering: "-cv_id",
          search: search || undefined,
          ...(status ? { status } : {}),
          ...(requirement ? { requirement } : {}),
          ...(skillIds.length ? { skill: skillIds } : {}),
        },
      })).data,
  });
}

export function useCreateCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => (await api.post("/candidates/", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

function _invalidateCandidate(qc: ReturnType<typeof useQueryClient>, id: number) {
  qc.invalidateQueries({ queryKey: ["candidate-detail", id] });
  qc.invalidateQueries({ queryKey: ["candidates"] });
  qc.invalidateQueries({ queryKey: ["dashboard"] });
}

/** Mark a candidate Fake / Blacklisted (mandatory reason). Mutually exclusive. */
export function useSetCandidateStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status_code, reason }: { id: number; status_code: string; reason: string }) =>
      (await api.post(`/candidates/${id}/set-status/`, { status_code, reason })).data,
    onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
  });
}

/** Verify & update the MASTER candidate profile (recruiter/admin). */
export function useVerifyCandidateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: number } & Record<string, unknown>) =>
      (await api.post(`/candidates/${id}/verify-profile/`, payload)).data,
    onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
  });
}

/** Add a candidate to one or more requirements' Review Pools ("under review").
 *  Explicit pre-pipeline tag — never creates a jd_cv_mapping. §9: only the
 *  requirement's assigned recruiter (or an admin) may tag. */
export function useTagRequirement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, requirementIds }: { id: number; requirementIds: number[] }) =>
      (await api.post(`/candidates/${id}/tag-requirements/`, { requirement_ids: requirementIds })).data,
    onSuccess: (_data, vars) => {
      _invalidateCandidate(qc, vars.id);
      qc.invalidateQueries({ queryKey: ["new-cvs"] }); // review pool
    },
  });
}

/** Remove a candidate from a requirement's Review Pool. */
export function useUntagRequirement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, requirement }: { id: number; requirement: number }) =>
      (await api.post(`/candidates/${id}/untag-requirement/`, { requirement })).data,
    onSuccess: (_data, vars) => {
      _invalidateCandidate(qc, vars.id);
      qc.invalidateQueries({ queryKey: ["new-cvs"] });
    },
  });
}

/** Admin: remove a Fake / Blacklisted mark → restore the candidate to Talent Pool. */
export function useClearCandidateStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason?: string }) =>
      (await api.post(`/candidates/${id}/clear-status/`, { reason })).data,
    onSuccess: (_data, vars) => _invalidateCandidate(qc, vars.id),
  });
}

export type BulkRowStatus = "VALID" | "INVALID" | "DUPLICATE" | "UPDATE" | "CREATED" | "UPDATED" | "ERROR";

export interface BulkRow {
  excel_row: number;
  name: string;
  mobile: string;
  email: string;
  status: BulkRowStatus;
  errors: string[];
  warnings: string[];
  duplicate?: { existing_cv_serial: string; existing_cv_id: number } | null;
}

export interface BulkSummary {
  total: number;
  valid: number;
  update: number;
  duplicate: number;
  invalid: number;
  warnings: number;
}

export interface DuplicateFileInfo {
  batch_id: number;
  file_name: string | null;
  created_on: string | null;
}

export interface BulkPreview {
  ok: boolean;
  error?: string;
  batch_id?: number | null;   // DRAFT batch to confirm at import (Feature 5a)
  header_row?: number;
  summary?: BulkSummary;
  rows: BulkRow[];
  duplicate_file?: DuplicateFileInfo | null;
}

export interface BulkImportReport {
  ok: boolean;
  error?: string;
  created: number;
  updated: number;
  possible_duplicates: { row: number; mobile: string; existing_cv_serial: string }[];
  skipped: { row: number; errors: string[] }[];
  warnings: { row: number; messages: string[] }[];
  rows: BulkRow[];
  duplicate_file?: DuplicateFileInfo | null;
}

/** Validate-only preview — no DB writes. */
export function useBulkPreview() {
  return useMutation({
    mutationFn: async ({ file }: { file: File }) => {
      const form = new FormData();
      form.append("file", file);
      return (await api.post<BulkPreview>("/candidates/bulk-preview/", form)).data;
    },
  });
}

/** Import valid rows. Preferred: confirm a preview DRAFT via `batchId` (imports the
 *  exact validated dataset). Fallback: a direct `file`. Optional requirement + source. */
export function useBulkImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ batchId, file, requirement, source }:
      { batchId?: number | null; file?: File; requirement?: string; source?: string }) => {
      const form = new FormData();
      if (batchId != null) form.append("batch_id", String(batchId));
      else if (file) form.append("file", file);
      if (requirement) form.append("requirement", requirement);
      if (source) form.append("source", source);
      return (await api.post<BulkImportReport>("/candidates/bulk-upload/", form)).data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      // The Import History dialog mounts (and fetches) as soon as the
      // Candidates page loads, well before any import happens, so without this
      // its list stays on that stale snapshot — a just-completed batch is
      // written to the DB (see confirm_import_batch/import_candidates_excel)
      // but never appears in "Import History" until something else happens to
      // invalidate this query. Invalidating it here is the fix.
      qc.invalidateQueries({ queryKey: ["import-batches"] });
    },
  });
}

// --- Duplicate Review workflow (separate from candidate status) --------------
export interface DuplicateReview {
  review_id: number;
  existing_candidate: number;
  existing_candidate_detail: {
    cv_id: number;
    cv_serial: string;
    candidate_name: string;
    mobile: string;
    email: string;
    current_company: string | null;
    candidate_status_name: string | null;
  } | null;
  new_candidate_name: string;
  new_mobile: string;
  new_email: string | null;
  detection_reason: string;
  review_status: "PENDING" | "RESOLVED";
  resolution: "MERGED" | "KEPT_SEPARATE" | "CORRECTED" | null;
  notes: string | null;
  created_by_name: string | null;
  created_on: string | null;
  resolved_by_name: string | null;
  resolved_on: string | null;
}

/** Admin-only list of duplicate reviews (optionally filtered by status). */
export function useDuplicateReviews(status?: "PENDING" | "RESOLVED") {
  return useQuery({
    queryKey: ["duplicate-reviews", status ?? "all"],
    queryFn: async () =>
      (await api.get<Paginated<DuplicateReview>>("/duplicate-reviews/", {
        params: { page_size: 100, ...(status ? { review_status: status } : {}) },
      })).data,
  });
}

/** Recruiter/Admin: submit a detected duplicate for Admin review. */
export function useCreateDuplicateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) =>
      (await api.post("/duplicate-reviews/", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["duplicate-reviews"] }),
  });
}

/** Admin: resolve a review (merge/keep-separate/correct). */
export function useResolveDuplicateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      (await api.post(`/duplicate-reviews/${id}/resolve/`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["duplicate-reviews"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
    },
  });
}

// --- Import batch history (Feature 2) ----------------------------------------
export interface ImportBatch {
  batch_id: number;
  batch_uid: string | null;
  uploaded_by_name: string | null;
  file_name: string | null;
  source_name: string | null;
  requirement_tracker_no: string | null;
  header_row: number | null;
  total_rows: number;
  created_count: number;
  updated_count: number;
  duplicate_count: number;
  skipped_count: number;
  status: "PENDING" | "COMPLETED" | "FAILED" | "ROLLED_BACK";
  created_on: string | null;
  completed_on: string | null;
}

/** Import history — own uploads for a recruiter, all for an admin. */
export function useImportBatches() {
  return useQuery({
    queryKey: ["import-batches"],
    queryFn: async () =>
      (await api.get<Paginated<ImportBatch>>("/import-batches/", { params: { page_size: 100 } })).data,
  });
}

/** Roll back a batch (soft-delete the untouched candidates it created). */
export function useRollbackImportBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id }: { id: number }) =>
      (await api.post<{ removed: string[]; kept: { cv_serial: string; reason: string }[]; removed_count: number; kept_count: number }>(
        `/import-batches/${id}/rollback/`, {})).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["import-batches"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export async function downloadBatchReport(id: number) {
  const res = await api.get(`/import-batches/${id}/report/`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `import_batch_${id}_report.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- Location reconciliation (Feature 3) -------------------------------------
export interface UnmappedLocation {
  text: string;
  count: number;
  suggested_location_id: number | null;
  suggested_city: string | null;
}

/** Import "kept as text" locations still unmapped to Location Master. */
export function useUnmappedLocations(enabled = true) {
  return useQuery({
    queryKey: ["unmapped-locations"],
    enabled,
    queryFn: async () => (await api.get<UnmappedLocation[]>("/candidates/unmapped-locations/")).data,
  });
}

/** Map an unmapped location text to an existing Location Master city. */
export function useReconcileLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ text, location_id }: { text: string; location_id: number }) =>
      (await api.post<{ reconciled: number; location: string }>(
        "/candidates/reconcile-location/", { text, location_id })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unmapped-locations"] });
      qc.invalidateQueries({ queryKey: ["candidates"] });
    },
  });
}

export async function downloadCandidateTemplate() {
  const res = await api.get("/candidates/upload-template/", { responseType: "blob" });
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "candidate_upload_template.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}