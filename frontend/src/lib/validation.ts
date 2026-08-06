/**
 * Master-data validation & normalisation — the frontend mirror of the backend's
 * core/validation.py. Keeping the two in lockstep means the form shows the same
 * normalised value and the same error the server would produce, so Save is only
 * ever enabled when the server will accept the record. The backend remains the
 * source of truth; this is purely for instant, inline UX.
 */

export type NameKind = "place" | "person" | "handle" | "skill" | "alpha" | "alphaamp" | "label";
export type FieldKind = NameKind | "email" | "phone" | "code";
export type Casing = "upper" | "title" | "title_strict" | "trim";

const INVISIBLE = /[​‌‍⁠﻿]/g;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE_RE = /^[6-9]\d{9}$/;
const CODE_RE = /^[A-Za-z0-9_-]+$/;
const HAS_LETTER = /[A-Za-z]/;
const SPACE_AROUND_HYPHEN = /\s-|-\s/;

const NAME_PATTERNS: Record<NameKind, RegExp> = {
  place: /^[A-Za-z][A-Za-z '-]*$/,
  person: /^[A-Za-z][A-Za-z '.-]*$/,
  handle: /^[A-Za-z0-9][A-Za-z0-9._-]*$/,
  skill: /^[A-Za-z0-9][A-Za-z0-9 .+#/'-]*$/,
  alpha: /^[A-Za-z][A-Za-z ]*$/, // letters + spaces (Priority)
  alphaamp: /^[A-Za-z][A-Za-z &-]*$/, // letters, spaces, hyphen, & (Work Mode / Req Type / Req Status)
  label: /^[A-Za-z0-9][A-Za-z0-9 &/().,'-]*$/,
};

// Canonical capitalisation for common technical terms (mirror of the backend
// CANONICAL map). Keyed by the normalised (collapsed, lower-cased) form.
const CANONICAL: Record<string, string> = {
  sql: "SQL", mysql: "MySQL", postgresql: "PostgreSQL", postgres: "PostgreSQL",
  mongodb: "MongoDB", github: "GitHub", gitlab: "GitLab",
  "power bi": "Power BI", powerbi: "Power BI", "ms excel": "MS Excel",
  aws: "AWS", azure: "Azure", gcp: "GCP",
  react: "React", reactjs: "ReactJS", "react.js": "ReactJS",
  "node.js": "Node.js", nodejs: "Node.js", "node js": "Node.js",
  javascript: "JavaScript", typescript: "TypeScript",
  html: "HTML", css: "CSS", scss: "SCSS",
  "rest api": "REST API", "rest apis": "REST APIs", graphql: "GraphQL",
  "ui/ux": "UI/UX", ui: "UI", ux: "UX",
  ".net": ".NET", php: "PHP", json: "JSON", xml: "XML",
  api: "API", apis: "APIs", devops: "DevOps", "ci/cd": "CI/CD",
  ios: "iOS",
};

/** Capitalise one token, preserving acronyms + intentional internal caps. */
function titleToken(w: string): string {
  if (!w) return w;
  if (w === w.toUpperCase()) return w.length <= 4 ? w : w[0] + w.slice(1).toLowerCase();
  if (w.slice(1) !== w.slice(1).toLowerCase()) return w; // internal capital (ReactJS)
  return w[0].toUpperCase() + w.slice(1);
}

/** Title Case with canonical/acronym awareness (mirror of backend title_case). */
function titleCase(s: string): string {
  return s.split(" ").map(titleToken).join(" ");
}

/** Strict Title Case for place names (mirror of backend strict_title_case):
 *  lower-case then capitalise the first letter of each word, incl. after
 *  hyphens/apostrophes. "mUMBAI"->"Mumbai", "o'fallon"->"O'Fallon". */
function strictTitleCase(s: string): string {
  return s.toLowerCase().replace(/(^|[ '-])([a-z])/g, (_m, sep, ch) => sep + ch.toUpperCase());
}

/** Clean text: drop invisible chars, NFKC, collapse whitespace, trim, + casing. */
export function normalizeText(value: string, mode?: Casing): string {
  let s = (value ?? "").replace(INVISIBLE, "").normalize("NFKC").replace(/ /g, " ");
  if (mode === "trim") return s.trim();
  s = s.replace(/\s+/g, " ").trim();
  if (mode === "upper") return s.toUpperCase();
  if (mode === "title_strict") return strictTitleCase(s);
  if (mode === "title") return CANONICAL[s.toLowerCase()] ?? titleCase(s);
  return s;
}

/** Comparison key for duplicate detection: normalised + lower-cased. */
export function normalizeKey(value: unknown): string {
  return normalizeText(String(value ?? "")).toLowerCase();
}

/** Derive a stable UPPER_SNAKE code from a display name — the frontend mirror of
 *  the backend `generate_code` (for the read-only preview during create).
 *  "Screening Scheduled" → "SCREENING_SCHEDULED". Backend is authoritative. */
export function generateCode(name: unknown): string {
  return normalizeText(String(name ?? ""))
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

const NAME_KINDS: NameKind[] = ["place", "person", "handle", "skill", "alpha", "alphaamp", "label"];

function validateName(value: string, kind: NameKind): string | null {
  const s = (value ?? "").trim();
  if (!s) return null;
  if (!HAS_LETTER.test(s)) return "Must contain letters; numbers or symbols alone aren't allowed.";
  if (s.includes("--")) return "Remove the repeated hyphen.";
  if (s.startsWith("-") || s.endsWith("-")) return "Cannot start or end with a hyphen.";
  if (SPACE_AROUND_HYPHEN.test(s)) return "A hyphen must join words directly, with no spaces around it.";
  if (!NAME_PATTERNS[kind].test(s)) return "Contains invalid characters.";
  return null;
}

export interface FieldRule {
  required?: boolean;
  kind?: FieldKind;
  maxLength?: number;
  label: string;
}

/** Validate a single value against its rule. Returns an error message or null. */
export function validateValue(value: unknown, rule: FieldRule): string | null {
  const s = typeof value === "string" ? value.trim() : value == null ? "" : String(value);
  if (!s) return rule.required ? `${rule.label} is required.` : null;
  if (rule.maxLength && s.length > rule.maxLength) return `Keep ${rule.label} to ${rule.maxLength} characters or fewer.`;
  if (rule.kind === "email") return EMAIL_RE.test(s) ? null : "Enter a valid email address.";
  if (rule.kind === "phone") return PHONE_RE.test(s) ? null : "Enter a valid 10-digit mobile number (starts 6-9).";
  if (rule.kind === "code") return CODE_RE.test(s) ? null : "Use only letters, numbers, hyphen or underscore.";
  if (rule.kind && NAME_KINDS.includes(rule.kind as NameKind)) return validateName(s, rule.kind as NameKind);
  return null;
}

// --------------------------------------------------------------------------- #
//  Duplicate & similarity detection (against the already-loaded rows)
// --------------------------------------------------------------------------- #
type Row = Record<string, unknown>;

/** Exact duplicate (case-/space-insensitive) on a set of fields. Returns the
 * matching row (active or inactive) or null. `fields` may be one field or a
 * composite set (e.g. city+state+country). */
export function findDuplicate(rows: Row[], fields: string[], values: Row, excludePk?: unknown, pkField?: string): Row | null {
  const target = fields.map((f) => normalizeKey(values[f]));
  if (target.some((v) => v === "")) return null;
  for (const row of rows) {
    if (pkField && excludePk != null && row[pkField] === excludePk) continue;
    if (fields.every((f, i) => normalizeKey(row[f]) === target[i])) return row;
  }
  return null;
}

function bigrams(s: string): Map<string, number> {
  const m = new Map<string, number>();
  for (let i = 0; i < s.length - 1; i++) {
    const g = s.slice(i, i + 2);
    m.set(g, (m.get(g) ?? 0) + 1);
  }
  return m;
}

/** Dice coefficient (0..1) on normalised bigrams. */
export function similarity(a: string, b: string): number {
  const x = normalizeKey(a);
  const y = normalizeKey(b);
  if (!x || !y) return 0;
  if (x === y) return 1;
  if (x.length < 2 || y.length < 2) return 0;
  const A = bigrams(x);
  const B = bigrams(y);
  let inter = 0;
  let total = 0;
  A.forEach((c, g) => {
    total += c;
    if (B.has(g)) inter += Math.min(c, B.get(g)!);
  });
  B.forEach((c) => (total += c));
  return (2 * inter) / total;
}

/** Rows whose `field` is similar (but not identical) to `value`. */
export function findSimilar(rows: Row[], field: string, value: unknown, excludePk?: unknown, pkField?: string, threshold = 0.7): Row[] {
  const v = String(value ?? "").trim();
  if (v.length < 3) return [];
  const key = normalizeKey(v);
  return rows.filter((row) => {
    if (pkField && excludePk != null && row[pkField] === excludePk) return false;
    const other = normalizeKey(row[field]);
    return other !== key && similarity(v, String(row[field] ?? "")) >= threshold;
  });
}
