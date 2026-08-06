/**
 * Extract a human-readable message from an Axios error.
 *
 * The backend wraps every error in a consistent envelope
 * (`core.exceptions.custom_exception_handler`):
 *
 *     { success: false, status_code: 400, error: { ...details... } }
 *
 * so the real payload lives under `error`. `error` may be `{ detail: "…" }`,
 * a field-error map (`{ field: ["msg"] }`), or a `{ code: "stale" }` marker.
 * Falls back to `fallback` when nothing usable is found.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: any } })?.response?.data;
  const body = data?.error ?? data;
  if (body?.code === "stale") return "This record was changed by someone else. Reload and try again.";
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail) && typeof body.detail[0] === "string") return body.detail[0];
  if (body && typeof body === "object") {
    const first = Object.values(body)[0];
    if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    if (typeof first === "string") return first;
  }
  return fallback;
}
