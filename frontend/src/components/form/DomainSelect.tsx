import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDomains } from "@/lib/lookups";
import { useAuth } from "@/auth/AuthContext";
import { MasterCreateDialog } from "@/components/form/MasterCreateDialog";

interface DomainSelectProps {
  value: number | null;
  onChange: (id: number | null) => void;
  invalid?: boolean;
  placeholder?: string;
  id?: string;
}

/**
 * Searchable single-select for a Skill's Domain, sourced from the Domain master
 * (active only). Admins additionally get a "+ Add Domain" action so a missing
 * domain can be created inline. Hiring Managers (creating a skill from the
 * Requirement form) get a read-only dropdown — they may select an existing
 * domain but never create one.
 */
export function DomainSelect({ value, onChange, invalid, placeholder = "Select domain…", id }: DomainSelectProps) {
  const domains = useDomains();
  const { user } = useAuth();
  const canCreate = user?.role.code === "ADM"; // domains are Admin-only controlled data
  const [open, setOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const all = useMemo(
    () => [...(domains.data ?? [])].sort((a, b) => a.domain_name.localeCompare(b.domain_name)),
    [domains.data]
  );
  const selected = useMemo(() => all.find((d) => d.domain_id === value) ?? null, [all, value]);

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter((d) => !q || d.domain_name.toLowerCase().includes(q));
  }, [all, query]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (open) (listRef.current?.children[active] as HTMLElement | undefined)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function pick(domainId: number) {
    onChange(domainId);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (options[active]) pick(options[active].domain_id);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <div
        onClick={() => {
          setOpen(true);
          inputRef.current?.focus();
        }}
        className={cn(
          "flex min-h-10 w-full items-center gap-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm focus-within:ring-2 focus-within:ring-ring",
          invalid && "border-destructive focus-within:ring-destructive"
        )}
      >
        <input
          ref={inputRef}
          id={id}
          value={open ? query : selected ? selected.domain_name : ""}
          disabled={domains.isLoading}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        />
        {value != null && (
          <button
            type="button"
            aria-label="Clear domain"
            onClick={(e) => {
              e.stopPropagation();
              onChange(null);
              setQuery("");
            }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-elevated">
          <ul ref={listRef} role="listbox" className="max-h-56 overflow-y-auto p-1">
            {domains.isLoading ? (
              <li className="px-2 py-2 text-sm text-muted-foreground">Loading domains…</li>
            ) : options.length === 0 ? (
              <li className="px-2 py-2 text-sm text-muted-foreground">
                {all.length === 0 ? "No active domains in the master" : "No matches"}
              </li>
            ) : (
              options.map((d, i) => (
                <li
                  key={d.domain_id}
                  role="option"
                  aria-selected={d.domain_id === value}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(d.domain_id)}
                  className={cn(
                    "cursor-pointer rounded-sm px-2 py-1.5 text-sm",
                    i === active && "bg-accent",
                    d.domain_id === value && "font-medium"
                  )}
                >
                  {d.domain_name}
                </li>
              ))
            )}
          </ul>
          {canCreate && (
            <div className="border-t p-1">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setAddOpen(true);
                }}
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm font-medium text-primary hover:bg-accent"
              >
                <Plus className="h-4 w-4" />
                {query.trim() ? `Add “${query.trim()}” as a new domain` : "Add Domain"}
              </button>
            </div>
          )}
        </div>
      )}

      {canCreate && (
        <MasterCreateDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          configKey="domains"
          prefill={{ domain_name: query.trim() }}
          onCreated={(domain) => {
            onChange(domain.domain_id as number);
            setQuery("");
          }}
        />
      )}
    </div>
  );
}
