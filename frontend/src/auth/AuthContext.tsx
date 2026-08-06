import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setAuthToken, STORAGE_KEY } from "@/api/client";
import type { AuthUser } from "@/lib/types";

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  initialising: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [initialising, setInitialising] = useState(true);
  // AuthProvider sits inside QueryClientProvider, so the client is available.
  // The query cache is per-tab and outlives login/logout (no page reload), so
  // it MUST be purged on every auth boundary — otherwise the next user inherits
  // the previous user's cached, role-scoped data (e.g. the dashboard renders
  // from a stale `["dashboard"]` entry belonging to a different role).
  const queryClient = useQueryClient();

  // On first load, restore a stored session ONLY after the backend confirms the
  // token is still valid. A token in localStorage is never trusted on its own —
  // if it's missing/corrupt, invalid (401), or unverifiable (backend down), we
  // clear it and stay logged out so the app lands on the Login page.
  useEffect(() => {
    let active = true;
    const raw = localStorage.getItem(STORAGE_KEY);
    let stored: { user: AuthUser; token: string } | null = null;
    try {
      stored = raw ? (JSON.parse(raw) as { user: AuthUser; token: string }) : null;
    } catch {
      stored = null;
    }

    if (!stored?.token) {
      localStorage.removeItem(STORAGE_KEY);
      setInitialising(false);
      return;
    }

    // Send the token so /auth/me/ can verify it, but don't mark authenticated yet.
    setAuthToken(stored.token);

    api
      .get("/auth/me/", { timeout: 8000 }) // fail fast if the backend hangs
      .then(({ data }) => {
        if (!active) return;
        setUser(data);
        setToken(stored!.token);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: data, token: stored!.token }));
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        setToken(null);
        setAuthToken(null);
        localStorage.removeItem(STORAGE_KEY);
      })
      .finally(() => {
        if (active) setInitialising(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function login(username: string, password: string) {
    const { data } = await api.post("/auth/login/", { username, password });
    // Drop any queries cached under a prior identity BEFORE the new user's
    // screens mount, so the first render fetches fresh, correctly-scoped data
    // instead of serving a previous user's cached result.
    queryClient.clear();
    setUser(data.user);
    setToken(data.token);
    setAuthToken(data.token);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: data.user, token: data.token }));
  }

  function logout() {
    setUser(null);
    setToken(null);
    setAuthToken(null);
    localStorage.removeItem(STORAGE_KEY);
    // Wipe this user's cached data so the next login on the same tab starts clean.
    queryClient.clear();
  }

  const value = useMemo(
    () => ({ user, token, initialising, login, logout }),
    [user, token, initialising]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
