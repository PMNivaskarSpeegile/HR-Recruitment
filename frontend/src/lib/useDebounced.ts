import { useEffect, useState } from "react";

/**
 * Returns a debounced copy of `value` that only updates after `ms` of quiet.
 * Used to throttle server-backed search inputs (list tables, searchable
 * requirement/candidate pickers) so we don't fire a request per keystroke.
 */
export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
