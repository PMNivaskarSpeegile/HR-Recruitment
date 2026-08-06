import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export type ResourceRow = Record<string, any>;

interface Paginated<T> {
  results: T[];
}

export function useResourceList(endpoint: string, activeOnly = false) {
  return useQuery({
    queryKey: ["resource", endpoint, activeOnly],
    queryFn: async () => {
      const params: Record<string, unknown> = { page_size: 200 };
      if (activeOnly) params.is_active = true; // dropdowns hide inactive rows
      return (await api.get<Paginated<ResourceRow>>(endpoint, { params })).data.results;
    },
  });
}

export function useResourceMutations(endpoint: string, pk: string) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["resource", endpoint] });
    qc.invalidateQueries({ queryKey: ["master"] }); // refresh lookup dropdowns elsewhere
  };
  const create = useMutation({
    mutationFn: async (body: ResourceRow) => (await api.post(endpoint, body)).data,
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: async (body: ResourceRow) => (await api.patch(`${endpoint}${body[pk]}/`, body)).data,
    onSuccess: invalidate,
  });
  // Soft delete (deactivate).
  const remove = useMutation({
    mutationFn: async (id: number) => (await api.delete(`${endpoint}${id}/`)).data,
    onSuccess: invalidate,
  });
  // Permanent delete — backend 409s if the row is referenced.
  const purge = useMutation({
    mutationFn: async (id: number) => (await api.delete(`${endpoint}${id}/permanent/`)).data,
    onSuccess: invalidate,
  });
  return { create, update, remove, purge };
}

export interface ReferenceInfo {
  referenced: boolean;
  total: number;
  details: { entity: string; count: number }[];
}

/** What references a row — drives the delete dialog (deactivate vs permanent). */
export async function fetchReferences(endpoint: string, id: number): Promise<ReferenceInfo> {
  return (await api.get<ReferenceInfo>(`${endpoint}${id}/references/`)).data;
}
