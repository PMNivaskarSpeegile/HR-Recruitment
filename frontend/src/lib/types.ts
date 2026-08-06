export type Role = "ADM" | "REC" | "HM";

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface AuthUser {
  user_id: number;
  full_name: string;
  username: string;
  email: string;
  role: { id: number; code: Role; name: string };
}
