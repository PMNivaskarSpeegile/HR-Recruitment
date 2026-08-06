# ATS Design System

The single source of truth for the frontend's visual language and shared components.
**Rule:** never introduce a color, spacing value, type style, or component variant that isn't defined here. Add it here first, then use it. Reuse components; refactor duplicates instead of forking.

Status legend: ✅ built · 📋 planned (built during screen implementation)

---

## 1. Color tokens  ✅ implemented
Defined as HSL triplets in `src/index.css` (so Tailwind opacity modifiers like `bg-primary/10` work), surfaced as Tailwind colors in `tailwind.config.js`.

| Token (Tailwind class) | Hex | Usage |
|---|---|---|
| `background` | `#F8FAFC` | App background |
| `card` / `popover` | `#FFFFFF` | Surfaces, cards, menus |
| `foreground` | `#0F172A` | Primary text |
| `muted-foreground` | `#475569` | Secondary text |
| `primary` | `#2563EB` | Primary actions, links, active nav |
| `primary-dark` | `#1E40AF` | Pressed/hover emphasis, charts |
| `teal` | `#14B8A6` | Accent / in-progress states |
| `success` | `#16A34A` | Positive states |
| `warning` | `#F59E0B` | Caution states |
| `destructive` | `#DC2626` | Danger / errors |
| `secondary` / `accent` / `muted` | `#F1F5F9` | Neutral surfaces, hovers |
| `border` / `input` | `#E2E8F0` | Borders, dividers, inputs |
| `ring` | `#2563EB` | Focus ring |
| `sidebar` | `#0F172A` | Dark left sidebar |
| `sidebar-foreground` | `#E2E8F0` | Sidebar text |
| `sidebar-muted` | `#94A3B8` | Sidebar inactive |

Semantic colors only — no raw hex in components.

## 2. Typography  ✅ (Inter)
Font: **Inter Variable** (`@fontsource-variable/inter`), `font-sans`.

| Role | Class |
|---|---|
| Page title | `text-2xl font-semibold tracking-tight` |
| Section title | `text-lg font-semibold` |
| Card title | `text-base font-semibold` |
| Body | `text-sm` |
| Caption | `text-xs text-muted-foreground` |

## 3. Spacing — 8px grid
Use Tailwind scale (`1`=4px, `2`=8px, `4`=16px, `6`=24px, `8`=32px). Page padding `p-6`; card padding `p-6`; control gap `gap-2`/`gap-4`.

## 4. Radius & shadows  ✅
- Radius: `--radius: 0.5rem` → `rounded-lg/md/sm`.
- Shadows: `shadow-card` (resting), `shadow-elevated` (modals/popovers).

## 5. Animation  ✅ tokens
`animate-fade-in`, `animate-slide-up` (subtle, 200ms). No flashy motion.

## 6. Iconography
**Lucide React** only. Icons must carry meaning (no decoration). 16px in dense UI, 18–20px in nav.

---

## 7. Layout architecture
`AppShell`: fixed dark **Sidebar** → sticky **Topbar** → **PageHeader** (title + description + primary action) → scrollable **Content**. Sidebar fixed; topbar sticky; only content scrolls.
- **Built ✅:** `AppShell` (`src/layouts/`), `Sidebar`, `Topbar`, `PageHeader` (`src/components/layout/`).
- **Not yet built 📋:** `NavItem`, `Breadcrumbs`, `Toolbar` (nav items are inlined in `Sidebar`; per-page toolbars are inlined via `DataTable`'s `toolbar` slot and page-level filter chips).

## 8. Component library

### Built ✅
`cn()`, `Button` (default/outline/secondary/ghost/destructive · sm/default/lg/icon), `Input`, `Label`, `Card` (+Header/Title/Description/Content/Footer), `Badge` (default/secondary/success/warning/danger/teal/muted/outline/blue/purple/orange/neutral — the last four are light-bg/dark-text palette colours used by the status maps, theme-aware via `dark:` variants), `Skeleton`, `Avatar`, `Checkbox`, `DropdownMenu`, `StatCard`, `ChartCard`, `StatusBarChart` (horizontal, semantic colours) + `DonutChart` (Recharts; see §12), `DataTable` (TanStack Table: search/sort/pagination/column-visibility/sticky/hover/skeleton/empty — **client-side by default**; opt into **server mode** by passing `serverPagination` `{pageIndex,pageSize,total,onPageChange}` + a controlled `search` `{value,onChange}`, which flips on `manualPagination`/`manualFiltering`, disables client sorting, and renders server-count pagination — used by the Requirements and Candidates pages), `Dialog` (+`DialogBody`; capped at 90vh with sticky header/footer + scrollable body, responsive width — never exceeds the viewport), `Sheet` (+`SheetHeader`/`SheetBody`/`SheetFooter`; right-side drawer, Radix-based, slide animation — used for the Candidate Details drawer, reusable), `Select`, `Combobox` (dependency-free searchable single-select; powers `CountrySelect`/`StateSelect` over the shared `lib/geo` lists), `SkillMultiSelect` (searchable multi-select chips, sourced from the Skills Master via `useSkills`; role-gated "+ Add new skill" footer for ADM/HM — pass `allowCreate={false}` to suppress the create footer when the control is used purely as a filter; optional `max` cap), `LocationSelect` (searchable single-select over the Locations Master with the same role-gated "+ Add new location" footer), `DomainSelect` (searchable single-select over the Domain Master for a Skill's classification; **Admin-only** "+ Add Domain" footer — HMs select only), `MasterCreateDialog` (generic create-only inline master dialog parameterised by a config key — used by the "+ Add" footers; reuses the same validation/normalisation/dedup as the Admin Master Data form via the shared `useMasterForm` hook; ADM/HM only, status forced Active. Newer props: `dropTargetField` (a text field that accepts a dragged `text/plain` payload — a dropped value REPLACES the field, stays editable — used to drag an unmapped city onto the City input), `allowMultiple` ("save & add another": stays open and resets after each create, footer shows a running "Added N: …" list and a "Done"/"Cancel" toggle), and an optional `aside` slot (read-only reference panel beside the form, e.g. the list of unmapped locations; widens the dialog to `max-w-2xl`)), `RequirementSelect` (`features/requirements/RequirementSelect.tsx` — async, server-backed, debounced searchable single-select for requirements; replaced the old client-side list capped at 100 rows so any requirement is findable by tracker/role/client; role-scoped on the backend; caches the chosen row and resolves an externally-set value via a single fetch; `clearable`/`clearLabel`, `invalid`, `disabled` props; used across the Requirements, Pipeline, CandidateForm, BulkUpload and Candidates pages), `Textarea`, `Tabs`, `Toaster` (sonner), `FormSelect` (shared RHF-bound select). Forms use React Hook Form + Zod. Master-data lookup hooks live in `lib/lookups.ts` (single source). Layout: `Sidebar`, `Topbar`, `PageHeader`, `AppShell`. Helpers: `lib/status.ts` (status→Badge + candidate/position status maps and labels), `lib/chart.ts`, `lib/format.ts`, `lib/brand.ts`, `lib/apiError.ts` (`apiErrorMessage(err, fallback)` — unwraps the backend's `{ success, status_code, error }` envelope to a human message, incl. the `stale`/optimistic-lock case; used across ~13 dialogs for consistent server-error surfacing), and the `useDebounced(value, ms=300)` hook (`lib/useDebounced.ts` — throttles server-backed search inputs; used by `DataTable` server-mode callers and `RequirementSelect`).

### Planned 📋 (Radix-based, added during implementation)
- **Inputs:** `Select`, `Textarea`, `Checkbox`, `Switch`, `RadioGroup`, `DatePicker`
- **Overlays:** `Dialog`/`Modal`, `Sheet`/`Drawer`, `Tooltip`, `DropdownMenu`, `Popover` — note: a real Radix `Tooltip` is still **not** used; the bulk-upload and badge hover hints are native `title` attributes.
- **Feedback:** `Toast` (sonner), `Alert`, `EmptyState`, `Spinner`
- **Data:** `DataTable` (search · sort · filter · pagination · column visibility · sticky header · bulk actions · row hover · quick actions · loading skeleton · empty state), `Pagination`, `SearchBar`, `FilterBar`
- **Misc:** `Avatar`, `Separator`, `Tabs`, `ChartCard` (Recharts wrapper), `KanbanBoard` (pipeline)
- **Forms:** `Form*` wrappers integrating React Hook Form + Zod (inline validation, required markers, error/success states)

> New Radix deps to install at implementation: `@radix-ui/react-dialog`, `-dropdown-menu`, `-tooltip`, `-popover`, `-select`, `-checkbox`, `-switch`, `-tabs`, `-avatar`, `-separator`; `sonner` (toasts). Optionally `@tanstack/react-table` for `DataTable`.

## 9. Data & forms stack  ✅ wired
- **TanStack Query** — all server state (caching, loading/error, invalidation). `QueryClient` configured in `main.tsx`.
- **Axios** client (`src/api/client.ts`) — JWT + 401 handling.
- **React Hook Form + Zod** — all forms; schema-driven validation.
- **Recharts** — all charts; semantic colours via `lib/chart.ts` (see §12). `DonutChart` (distributions) + `StatusBarChart` (horizontal, dynamic height).

## 10. Status → Badge mapping (consistency)
Always render ATS statuses via `<Badge>` — the mapping lives in `lib/status.ts`. Name-based badges use `statusVariant(name)`; candidate profile-status badges use `candidateStatusVariant(code)` (keyed by CODE so the colour is identical everywhere) and their label comes from `candidateStatusLabel(code, name)`; position (seat) badges use `positionStatusVariant(code)`. The name map is kept in lock-step with the code map so dashboard (name) badges match the Candidates page (code).

| Requirement status | Variant | | CV / pipeline status | Variant |
|---|---|---|---|---|
| New | `muted` | | Shortlisted | `default` |
| Assigned | `default` | | JD Email Sent | `teal` |
| Open | `teal` | | Schedule Screening | `warning` |
| Hold | `warning` | | Screening Scheduled | `default` |
| Partial Filled | `default` | | OK to Proceed | `success` |
| Close Filled / Filled | `success` | | Rejected / Fake | `danger` |
| Close Lost / Cancelled | `danger` | | Not Suitable / Not Relevant / Dropped / Withdrawn | `muted` |
| Expired | `muted` | | No Response | `warning` |
| | | | Possible Duplicate | `orange` |

**Candidate global status** (name → variant; the code-keyed map drives the actual badges):

| Candidate status | Variant | Notes |
|---|---|---|
| New CV | `blue` | system-assigned on capture |
| Talent Pool / Saved | `purple` | code `SAVED`; **relabelled "Talent Pool" in the UI** via `candidateStatusLabel` while the code stays `SAVED` |
| Reject Hold | `orange` | system 6-month cool-off |
| Joined | `success` | placed |
| Possible Duplicate | `orange` | system-assigned |
| Fake | `danger` | manually settable |
| Blacklisted | `neutral` | manually settable (dark gray) |

Position (seat) status: Open→`teal`, Hold→`warning`, Filled→`success`, Cancelled→`danger`, In Progress→`default`, Inactive→`muted`.

## 11. Accessibility
Contrast ≥ WCAG AA; visible focus ring (`ring`); keyboard-navigable (Radix primitives); labelled inputs; semantic headings. **Charts never rely on colour alone** — bars carry status labels + value labels; donut slices carry a text legend with counts; both have tooltips.

## 12. Chart status palette  ✅ implemented
Charts colour each status with a **semantic hue** (not a single flat colour) so stages are distinguishable at a glance. Defined once in `src/lib/chart.ts` (`STATUS_COLOR` map + `statusColor(name)` helper, keyed by status display-names); components import it — no raw hex in chart components.

| Requirement status | Colour | | Pipeline status | Colour |
|---|---|---|---|---|
| Open | `#2563EB` blue | | Shortlisted | `#7C3AED` purple |
| Assigned | `#4F46E5` indigo | | JD Email Sent | `#14B8A6` teal |
| Partial Filled | `#14B8A6` teal | | Schedule Screening | `#F59E0B` orange |
| Close Filled | `#16A34A` green | | Screening Scheduled | `#06B6D4` cyan |
| Hold | `#F59E0B` orange | | OK to Proceed | `#16A34A` green |
| Cancelled | `#DC2626` red | | Rejected | `#DC2626` red |
| Close Lost | `#B91C1C` dark red | | Not Suitable | `#991B1B` dark red |
| New / Expired | `#94A3B8` / `#64748B` slate | | Fake | `#92400E` brown |
| | | | Dropped / No Response | `#64748B` / `#94A3B8` slate |

Future stages (Interview Scheduled/Completed `#06B6D4`/`#2563EB`, Offer Released `#10B981`, Joined `#065F46`) are pre-mapped so they slot in automatically. Unknown statuses fall back to slate `#94A3B8`.

**Chart components**
- `DonutChart` — categorical distribution (requirements by status); semantic slices, centre total, legend with **status + count** (no truncation; full name on hover). Percentages live in a professional hover **tooltip** (name + count + percentage); the hovered slice enlarges (Material "active" emphasis).
- `StatusBarChart` — horizontal bars (pipeline by stage); semantic per-bar colour, value labels at bar end, rounded corners, subtle dashed grid; **height grows with category count** (44px/row) so many stages are never compressed.
- `RecruiterWorkloadChart` — grouped vertical bars (per recruiter: requirements vs. candidates in pipeline); two series colours (`primary` blue / `teal`), value labels, legend.
- `ChartCard` — header (title + optional subtitle) over a flexible body; charts size themselves.

## 13. Screen-level patterns  ✅
- **Dashboard KPI tiles** — `StatCard`s with a `to` deep-link (`KPI_LINK`) that opens the relevant module list with a status/`missing` filter pre-applied. The destination list renders that filter as a single **dismissible filter chip** (with a "Clear filter" button); clearing it removes the query params.
- **Recruitment Ended / Expired banners & badges** — a requirement that has been ended early or has passed its date shows a status **badge** in the list/columns (`Recruitment Ended` / `Expired`) and an explanatory **banner** on its details page (who ended it, when, and what happened to the remaining positions).
- **Duplicate Review dialog** — the reviewer's two actions are relabelled for clarity: **"Update existing record"** (merge the submission into the matched candidate) and **"Ignore submission"** (discard the duplicate).
