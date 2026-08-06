import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSkills } from "@/lib/lookups";
import { useAuth } from "@/auth/AuthContext";
import { MasterCreateDialog } from "@/components/form/MasterCreateDialog";

interface SkillMultiSelectProps {
  value: number[]; // selected skill ids
  onChange: (ids: number[]) => void;
  max?: number; // optional cap (e.g. requirements have 3 slots)
  invalid?: boolean;
  placeholder?: string;
  id?: string;
  // Whether ADM/HM may add a missing skill inline. Default true (data-entry
  // forms); pass false when used purely as a filter (no create affordance).
  allowCreate?: boolean;
}

/**
 * Reusable searchable multi-select for skills, sourced from the Skills Master
 * (active only, cached + auto-refreshed via useSkills). Chips for selected
 * skills with individual remove + clear-all, type-to-filter, keyboard nav,
 * duplicate-proof, optional max. No hardcoded skill list.
 */
export function SkillMultiSelect({ value, onChange, max, invalid, placeholder = "Select skills…", id, allowCreate = true }: SkillMultiSelectProps) {
  const skills = useSkills();
  const { user } = useAuth();
  // Admins and Hiring Managers may add a missing skill inline; recruiters (who
  // also use this control on the candidate form) get the master as-is. Callers
  // using this purely as a filter pass allowCreate={false}.
  const canCreate = allowCreate && (user?.role.code === "ADM" || user?.role.code === "HM");
  const [open, setOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const all = useMemo(
    () => [...(skills.data ?? [])].sort((a, b) => a.skill_name.localeCompare(b.skill_name)),
    [skills.data]
  );
  const selected = useMemo(() => all.filter((s) => value.includes(s.skill_id)), [all, value]);
  const atMax = max != null && value.length >= max;

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter((s) => !value.includes(s.skill_id) && (!q || s.skill_name.toLowerCase().includes(q)));
  }, [all, value, query]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (open) (listRef.current?.children[active] as HTMLElement | undefined)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function add(skillId: number) {
    if (atMax) return;
    onChange([...value, skillId]);
    setQuery("");
    setActive(0);
  }
  function remove(skillId: number) {
    onChange(value.filter((v) => v !== skillId));
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
      if (options[active]) add(options[active].skill_id);
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Backspace" && query === "" && value.length) {
      remove(value[value.length - 1]); // backspace removes the last chip
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <div
        onClick={() => {
          if (!atMax) setOpen(true);
          inputRef.current?.focus();
        }}
        className={cn(
          "flex min-h-10 w-full items-start gap-1 rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-within:ring-2 focus-within:ring-ring",
          invalid && "border-destructive focus-within:ring-destructive"
        )}
      >
        <div className="flex flex-1 flex-wrap items-center gap-1">
          {selected.map((s) => (
            <span key={s.skill_id} className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-xs">
              {s.skill_name}
              <button
                type="button"
                aria-label={`Remove ${s.skill_name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  remove(s.skill_id);
                }}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            id={id}
            value={query}
            disabled={skills.isLoading}
            onFocus={() => setOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
              setOpen(true);
            }}
            onKeyDown={onKeyDown}
            placeholder={selected.length === 0 ? placeholder : atMax ? "Limit reached" : "Add…"}
            className="min-w-[6rem] flex-1 bg-transparent py-0.5 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
          />
        </div>
        <div className="flex items-center gap-1 pt-0.5">
          {value.length > 0 && (
            <button
              type="button"
              aria-label="Clear all skills"
              onClick={(e) => {
                e.stopPropagation();
                onChange([]);
              }}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </div>
      </div>

      {open && !atMax && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-elevated">
          <ul ref={listRef} role="listbox" aria-multiselectable className="max-h-56 overflow-y-auto p-1">
            {skills.isLoading ? (
              <li className="px-2 py-2 text-sm text-muted-foreground">Loading skills…</li>
            ) : options.length === 0 ? (
              <li className="px-2 py-2 text-sm text-muted-foreground">
                {all.length === 0 ? "No active skills in the master" : "No matches"}
              </li>
            ) : (
              options.map((s, i) => (
                <li
                  key={s.skill_id}
                  role="option"
                  aria-selected={false}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => add(s.skill_id)}
                  className={cn("cursor-pointer rounded-sm px-2 py-1.5 text-sm", i === active && "bg-accent")}
                >
                  {s.skill_name}
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
                {query.trim() ? `Add “${query.trim()}” as a new skill` : "Add new skill"}
              </button>
            </div>
          )}
        </div>
      )}

      {canCreate && (
        <MasterCreateDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          configKey="skills"
          prefill={{ skill_name: query.trim() }}
          onCreated={(skill) => {
            if (max == null || value.length < max) onChange([...value, skill.skill_id as number]);
            setQuery("");
          }}
        />
      )}

      {max != null && (
        <p className="mt-1 text-xs text-muted-foreground">
          {value.length}/{max} selected
        </p>
      )}
    </div>
  );
}
