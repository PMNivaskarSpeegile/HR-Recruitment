import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export const STORAGE_KEY = "ats_auth";

// No default Content-Type: axios sets application/json for object bodies and
// multipart/form-data (with boundary) for FormData uploads automatically.
export const api = axios.create({ baseURL });

/** Attach (or clear) the JWT used on every request. */
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

// On an expired/invalid token, clear session and bounce to login.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      localStorage.removeItem(STORAGE_KEY);
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
