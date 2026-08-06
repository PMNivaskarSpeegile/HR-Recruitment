import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDebounced } from "@/lib/useDebounced";
import { useRequirements, useRequirement } from "./api";
import type { Requirement } from "./types";

interface RequirementSelectProps {
  /** Selected req_id as a string, or "" for none. */
  value: string;
  /** Fires with the id ("" when cleared) and the full row (null when cleared). */
  onChange: (id: string, req: Requirement | null) => void;
  placeholder?: string;
  /** Adds a "clear" option at the top of the list (e.g. "All requirements"). */
  clearable?: boolean;
  clearLabel?: string;
  disabled?: boolean;
  invalid?: boolean;
  id?: string;
}

const label = (r: Requirement) => `${r.req_tracker_no} · ${r.jd_role_name}`;

/**
 * Async, server-backed searchable single-select for requirements. Replaces the
 * old dropdowns that read a client-side list capped at 100 rows — so a
 * requirement outside the newest 100 is now findable by typing its tracker,
 * role or client. Role-scoped on the backend (recruiters see only their
 * assigned requirements). Dependency-free, styled like Select/Combobox.
 */
export function RequirementSelect({
  value,
  onChange,
  placeholder = "Select a requirement",
  clearable = false,
  clearLabel = "None",
  disabled,
  invalid,
  id,
}: RequirementSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  // Remember the chosen row so the closed control shows its label without a
  // refetch. Also lets us surface the label for a value set before any search.
  const [selected, setSelected] = useState<Requirement | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const search = useDebounced(query.trim(), 300);
  const list = useRequirements({ search, pageSize: 20, enabled: open });
  const results = list.data?.results ?? [];

  // Resolve the label for an externally-set value we haven't cached (value set
  // without going through choose(), e.g. restored state). Cheap single fetch.
  const needsResolve = !!value && (!selected || String(selected.req_id) !== value);
  const resolved = useRequirement(needsResolve ? value : null);
  useEffect(() => {
    if (needsResolve && resolved.data) setSelected(resolved.data);
  }, [needsResolve, resolved.data]);
  useEffect(() => {
    if (!value) setSelected(null); // cleared externally
  }, [value]);

  // Close on outside click; reset the query & focus the box when opening.
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open]);

  function choose(r: Requirement) {
    setSelected(r);
    onChange(String(r.req_id), r);
    setOpen(false);
  }
  function clear() {
    setSelected(null);
    onChange("", null);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[active]) choose(results[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const display = value && selected ? label(selected) : "";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        id={id}
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          invalid && "border-destructive focus:ring-destructive",
        )}
      >
        <span className={cn("line-clamp-1 text-left", !display && "text-muted-foreground")}>
          {display || placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-elevated">
          <div className="flex items-center gap-2 border-b px-2.5">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
              placeholder="Search by ID, role or client…"
              className="h-9 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <ul role="listbox" className="max-h-60 overflow-y-auto p-1">
            {clearable && (
              <li
                role="option"
                aria-selected={!value}
                onMouseEnter={() => setActive(-1)}
                onClick={clear}
                className="flex cursor-pointer items-center justify-between rounded-sm px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent"
              >
                <span>{clearLabel}</span>
                {!value && <Check className="h-4 w-4 text-primary" />}
              </li>
            )}
            {list.isLoading ? (
              <li className="px-2 py-2 text-center text-sm text-muted-foreground">Searching…</li>
            ) : results.length === 0 ? (
              <li className="px-2 py-2 text-center text-sm text-muted-foreground">No requirements match</li>
            ) : (
              results.map((r, i) => (
                <li
                  key={r.req_id}
                  role="option"
                  aria-selected={String(r.req_id) === value}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(r)}
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm",
                    i === active && "bg-accent",
                  )}
                >
                  <span className="line-clamp-1">{label(r)}</span>
                  {String(r.req_id) === value && <Check className="h-4 w-4 shrink-0 text-primary" />}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
