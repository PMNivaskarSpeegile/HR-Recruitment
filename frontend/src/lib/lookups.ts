import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Paginated } from "@/lib/types";

function useMaster<T>(key: string, path: string) {
  return useQuery({
    queryKey: ["master", key],
    // Lookups power dropdowns across the app — only ever offer active records.
    queryFn: async () => (await api.get<Paginated<T>>(path, { params: { page_size: 200, is_active: true } })).data.results,
    staleTime: 5 * 60_000,
  });
}

export interface Client {
  client_id: number;
  client_name: string;
}
export interface ClientManager {
  client_mgr_id: number;
  manager_name: string;
  client: number;
}
export interface ReqType {
  req_type_id: number;
  req_type_name: string;
}
export interface LocationM {
  location_id: number;
  city: string;
  state: string;
  country?: string;
}
export interface Domain {
  domain_id: number;
  domain_name: string;
}
export interface Skill {
  skill_id: number;
  skill_name: string;
}
export interface NoticePeriod {
  np_id: number;
  np_name: string;
}
export interface Priority {
  priority_id: number;
  priority_name: string;
}
export interface SourceM {
  source_id: number;
  source_name: string;
}
export interface WorkMode {
  work_mode_id: number;
  work_mode_name: string;
}
export interface AppUser {
  user_id: number;
  full_name: string;
  role_code: string;
  is_active: boolean;
}
export interface RejectionReason {
  reason_id: number;
  reason_name: string;
}
export interface ScreeningMode {
  screening_mode_id: number;
  mode_name: string;
}

export const useClients = () => useMaster<Client>("clients", "/clients/");
export const useClientManagers = () => useMaster<ClientManager>("client-managers", "/client-managers/");
export const useReqTypes = () => useMaster<ReqType>("req-types", "/req-types/");
export const useLocations = () => useMaster<LocationM>("locations", "/locations/");
export const useSkills = () => useMaster<Skill>("skills", "/skills/");
export const useDomains = () => useMaster<Domain>("domains", "/domains/");
export const useNoticePeriods = () => useMaster<NoticePeriod>("notice-periods", "/notice-periods/");
export const usePriorities = () => useMaster<Priority>("priorities", "/priorities/");
export const useSources = () => useMaster<SourceM>("sources", "/sources/");
export const useWorkModes = () => useMaster<WorkMode>("work-modes", "/work-modes/");
export const useUsers = () => useMaster<AppUser>("users", "/users/");
export const useRejectionReasons = () => useMaster<RejectionReason>("rejection-reasons", "/rejection-reasons/");
export const useScreeningModes = () => useMaster<ScreeningMode>("screening-modes", "/screening-modes/");

// Inline creation of a missing skill/location from a workflow form is handled by
// components/form/MasterCreateDialog (it appends the created row to the relevant
// ["master", <key>] cache so it's instantly selectable). No bespoke hook needed.
