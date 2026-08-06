import { useCallback, useEffect, useMemo, useState } from "react";
import { findDuplicate, findSimilar, generateCode, normalizeText, validateValue } from "@/lib/validation";
import type { FieldRule } from "@/lib/validation";
import type { FieldDef, ResourceConfig } from "./config";
import type { ResourceRow } from "./api";

/** A finalised master Code: uppercase, starts with a letter, A–Z/0–9/_ only. */
const STRICT_CODE_RE = /^[A-Z][A-Z0-9_]*$/;

/** Map a config field to a validation rule (single source — see config.ts). */
export function ruleFor(f: FieldDef): FieldRule {
  return { required: f.required, kind: f.kind, maxLength: f.maxLength, label: f.label };
}

/**
 * Shared master-data form engine: value state, normalise-on-blur, live field
 * validation, duplicate / inactive-duplicate / similar detection and payload
 * assembly — all driven by a ResourceConfig + `lib/validation`. This is the
 * single source of truth consumed by BOTH the Admin Master Data form
 * (`ResourceForm`) and the inline create dialog (`MasterCreateDialog`) used on
 * the Requirement form, so the two always validate and format identically and a
 * future rule change in `config.ts`/`validation.ts` applies everywhere at once.
 */
export function useMasterForm({
  config,
  rows,
  open,
  initial = null,
}: {
  config: ResourceConfig;
  rows: ResourceRow[];
  open: boolean;
  initial?: ResourceRow | null;
}) {
  const isEdit = !!initial;
  const autoField = config.autoCode?.field;
  const autoSource = config.autoCode?.source;
  const [values, setValues] = useState<ResourceRow>({ is_active: true });
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  // On create the Code auto-follows the Name until the admin edits it once.
  const [codeEdited, setCodeEdited] = useState(false);

  /** Reset all fields to a blank (or `initial`) create form. Used on open and,
   *  for a "save & add another" flow, after each successful create. */
  const reset = useCallback(() => {
    const base: ResourceRow = { is_active: true };
    config.fields.forEach((f) => (base[f.name] = ""));
    if (initial) Object.assign(base, initial);
    setValues(base);
    setTouched({});
    setCodeEdited(false);
  }, [config, initial]);

  useEffect(() => {
    if (open) reset();
  }, [open, reset]);

  // Create mode: regenerate the Code from the Name until the user customises it.
  const sourceValue = autoSource ? values[autoSource] : undefined;
  useEffect(() => {
    if (!open || isEdit || !autoField || codeEdited) return;
    const gen = generateCode(sourceValue);
    setValues((v) => (v[autoField] === gen ? v : { ...v, [autoField]: gen }));
  }, [open, isEdit, autoField, codeEdited, sourceValue]);

  function setField(name: string, val: unknown) {
    setValues((v) => ({ ...v, [name]: val }));
  }

  /** The admin's one-time manual edit of the auto-generated code (create only).
   *  Stops further auto-regeneration from the name. */
  function editCode(val: string) {
    setCodeEdited(true);
    if (autoField) setValues((v) => ({ ...v, [autoField]: val }));
  }

  function blurField(f: FieldDef) {
    setTouched((t) => ({ ...t, [f.name]: true }));
    // Normalise text inputs on blur so the user sees exactly what will be saved
    // (codes upper-cased, places title-cased, whitespace collapsed). Body/
    // multiline and passwords are left untouched.
    if (f.type === "text") {
      setValues((v) => ({ ...v, [f.name]: normalizeText(String(v[f.name] ?? ""), f.casing) }));
    }
  }

  function setAllTouched() {
    setTouched(Object.fromEntries(config.fields.map((f) => [f.name, true])));
  }

  // --- live field errors -----------------------------------------------------
  const fieldErrors = useMemo(() => {
    const errs: Record<string, string> = {};
    for (const f of config.fields) {
      if (f.type === "password" && isEdit) continue; // optional on edit
      if (f.name === autoField) {
        // Frozen after creation → not validated on edit. On create it's a real,
        // editable field: required + strict UPPER_SNAKE format.
        if (isEdit) continue;
        const code = String(values[f.name] ?? "").trim();
        if (!code) errs[f.name] = `${f.label} is required.`;
        else if (!STRICT_CODE_RE.test(code))
          errs[f.name] = "Use UPPERCASE letters, numbers and underscores; start with a letter.";
        continue;
      }
      const e = validateValue(values[f.name], ruleFor(f));
      if (e) errs[f.name] = e;
    }
    return errs;
  }, [values, config, isEdit, autoField]);

  // --- duplicate / reactivate ------------------------------------------------
  const duplicate = useMemo(() => {
    for (const group of config.dedupeGroups ?? []) {
      // Only check once the group's fields are filled & individually valid.
      if (group.some((f) => !String(values[f] ?? "").trim() || fieldErrors[f])) continue;
      const match = findDuplicate(rows, group, values, initial?.[config.pk], config.pk);
      if (match) return { match, group };
    }
    return null;
  }, [rows, values, config, initial, fieldErrors]);

  const activeDup = duplicate && duplicate.match.is_active ? duplicate : null;
  const inactiveDup = duplicate && !duplicate.match.is_active ? duplicate : null;

  const similar = useMemo(() => {
    if (!config.similarField || duplicate) return [];
    return findSimilar(rows, config.similarField, values[config.similarField], initial?.[config.pk], config.pk).slice(0, 3);
  }, [rows, values, config, initial, duplicate]);

  const hasErrors = Object.keys(fieldErrors).length > 0;

  /** Assemble the normalised payload that will be sent to the API. */
  function buildPayload(): ResourceRow {
    const payload: ResourceRow = { is_active: !!values.is_active };
    config.fields.forEach((f) => {
      if (f.name === autoField && isEdit) return; // frozen after creation; backend ignores it
      const raw = f.type === "text" ? normalizeText(String(values[f.name] ?? ""), f.casing) : values[f.name];
      if (f.type === "password") {
        if (raw) payload[f.name] = raw;
      } else if (f.type === "number" || f.type === "select" || f.type === "domain") {
        payload[f.name] = raw === "" || raw == null ? null : Number(raw);
      } else {
        payload[f.name] = raw === "" ? null : raw;
      }
    });
    if (isEdit) {
      payload[config.pk] = initial![config.pk];
      // Optimistic-locking token: the row's last-known version.
      payload.expected_updated_on = initial!.updated_on ?? initial!.created_on ?? null;
    }
    return payload;
  }

  /** Human label for a field name (for duplicate messages). */
  const labelFor = (field: string) => config.fields.find((f) => f.name === field)?.label ?? field;

  return {
    isEdit,
    values,
    touched,
    setField,
    editCode,
    blurField,
    setAllTouched,
    fieldErrors,
    duplicate,
    activeDup,
    inactiveDup,
    similar,
    hasErrors,
    buildPayload,
    labelFor,
    reset,
  };
}
