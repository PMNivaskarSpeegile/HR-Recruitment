# Changelog

All notable changes per use case / milestone. Format loosely follows Keep a Changelog.

## [Infra/Docs] Docker + cloud deployment setup; documentation synced to current code
Prep for sharing the repo on GitHub / deploying.
- **Docker:** `docker-compose.yml` (Postgres 16 + Django/gunicorn + React built→nginx), `backend/Dockerfile` + `entrypoint.sh`, `frontend/Dockerfile` + `nginx.conf` (serves the SPA, proxies `/api` → backend), `.dockerignore`s, root + `frontend/.env.example`, and a `.gitattributes` (forces LF on `*.sh`/`*.sql` for cross-platform builds). `settings.py` gains WhiteNoise middleware + `STATIC_ROOT`/`STORAGES`; `requirements.txt` gains `gunicorn` + `whitenoise`. The db container loads `database/*.sql` (schema + reference data) on first start. New **`docs/DEPLOYMENT.md`** — local Docker run, env-var reference, cloud-hosting guide, pre-deploy checklist.
- **Cross-platform:** confirmed — env-driven config, no hardcoded paths; Python/Node/Postgres run on Windows/macOS/Linux (and the containers are Linux regardless of host).
- **DB scripts:** verified **NO DRIFT** (schema + 30 migrations match the models).
- **Docs refreshed to match code:** rewrote `API.md`, `DATABASE.md`, `RBAC.md`, `BULK_UPLOAD.md`, `DESIGN_SYSTEM.md`, `ARCHITECTURE.md`, `SEQUENCE_DIAGRAMS.md` (Stage×Outcome pipeline engine, pre-pipeline Review Pool, End Recruitment, requirement-closure cascade, bulk preview→confirm→rollback + location reconciliation, duplicate-review `UPDATED` resolution, corrected RBAC matrix, server-paginated `DataTable`, current table/status model, etc.); refreshed `database/migrations/README.md` history (added 0019, 0023–0030).
- **Verified:** `manage.py check` clean, `collectstatic` OK, dashboard tests green, `docker-compose.yml` parses, all Mermaid diagrams valid.

## [Candidates] Duplicate Review — consolidate resolution into "Update existing record" + "Ignore submission"
The three original actions were misleading and redundant: **Merge** was a no-op stub, **Keep separate** promised something the schema forbids (mobile is the unique identity key, so two candidates can't coexist with the same mobile, and the submitted row was never imported), and once Merge was made functional it did nearly the same DB write as **Correct identity**. Because there is only ever **one** real record, the two "edit the existing record" actions collapse into one.
- **Two clear outcomes now.**
  - **Update existing record** (resolution `UPDATED`) — one dialog with per-field *existing vs submitted* quick-picks (Name / Mobile / Email), each still editable; writes the chosen values onto the existing candidate and resolves. Covers both prior intents ("same person → adopt submitted info" and "fix a typo on the existing record"). Mobile/email are pre-checked against the UNIQUE constraints, so a value that belongs to a **different** candidate returns a clean 400 and leaves the review open.
  - **Ignore submission** (resolution `KEPT_SEPARATE`, shown as **"Ignored"**) — dismiss the review, keep the existing record untouched.
- **Backward compatible.** Legacy `MERGED`/`CORRECTED` remain valid resolutions (still apply the same write) so historical rows display correctly and older clients don't break; the UI now writes only `UPDATED`/`KEPT_SEPARATE`.
- **Verified:** 345 backend tests (Update writes chosen details & resolves; Update rejects an email owned by another candidate → 400, review stays pending; Ignore leaves the record untouched; legacy MERGED still resolves); `check`, `spectacular` (0 errors) clean; `tsc` + `vite build` clean. (Pre-existing unrelated flake `test_multiple_mobiles_uses_first_valid_with_warning` still fails independently.)

## [Candidates] Bulk-upload Validation Summary — verified counters + row-detail consistency
Audited the preview counters against every listed scenario and made the row-level detail match the badges.
- **Backend counting verified accurate (no logic change needed).** The status buckets **partition every data row exactly once** — `total = valid + update + duplicate + invalid` — and `total` excludes header/blank rows. Confirmed with 12 new scenario tests: all-valid; re-import same file (→ all *update*); DB duplicate (same mobile, different email → *duplicate*); intra-file duplicate mobile/email (2nd row → *invalid*); the same candidate twice; a validation-error row; a warning-only row (still *valid*); a warning **and** error row (*invalid*, also counted in warnings); a mixed file; and import skipping duplicates from the *created* count. `warnings` = **rows with one or more warnings** (row-consistent with the other badges — the requirement's "one badge per affected row" option), counted even on invalid rows.
- **Frontend consistency fix.** DUPLICATE rows were listed under **"Importable rows"** even though they are sent to review and never imported — so that list disagreed with the *Duplicates* badge and the "Import N" button. They now have their own **"Duplicates — sent to review (not imported)"** group; "Importable rows" shows only VALID + UPDATE, matching the button count exactly. Every badge got a tooltip stating precisely what it counts (Total = data rows excl. header/blank; Valid = new; Update = existing same mobile+email; Duplicate = same mobile/different email → review; Invalid = blocked; Warnings = rows with warnings).
- **Always current file, never cached.** Preview/import run through React Query **mutations** (no query cache); selecting a file or re-validating calls `resetOutputs()` first, so badges are recomputed from the current file on every validation and cleared when the file changes — no stale counts carry over.
- **Verified:** 341 backend tests (+12 counter scenarios); `tsc` + `vite build` clean. (Pre-existing unrelated flake `test_multiple_mobiles_uses_first_valid_with_warning` — a hardcoded mobile colliding with live dev-DB data — still fails independently.)

## [Candidates] Fix: alias map hid cities already in the master; auto-reconcile on create; clearer bulk-preview badge
Follow-ups on the Location Master / Unmapped Locations workflow.
- **Reconciliation root cause (the real one).** "Gurugram" (present in Location Master) still imported as *unmapped*. Cause: the curated city **alias map** rewrote `"gurugram" → "Gurgaon"` **unconditionally** — but the master row is literally "Gurugram", so the lookup for the alias canonical found nothing. (Normalization from the previous fix was correct but never got a chance — the alias mangled the name first.) **Fix:** `_resolve_location` now matches the city **as imported first**, and only falls back to the alias canonical when the literal name isn't in the master — so an alias never overrides a city that already exists. Alias values for Gurgaon/Gurugram now point to the master's actual spelling ("Gurugram") so **both** old/new spellings map. Normalized (NFKC/trim/collapse), case-insensitive, City+State+Country-aware, unique-active-only auto-map rules from the prior fix all still apply.
- **Auto-reconcile on create (no refresh).** When an admin drags an unmapped city onto the City field and creates the location, the app now **immediately reconciles** the candidates for that dragged text (and any unmapped rows whose normalized text equals the new city) via the existing reconcile endpoint. React Query invalidation drops the city from the Unmapped list, updates the candidate counts live, and shows the "No unmapped locations 🎉" empty state when the last one clears — all without a page refresh. The manual map-to-city flow is unchanged.
- **Bulk-preview badge clarified (not removed — it is meaningful).** "Will update" was ambiguous. It means: a candidate with the **same mobile & email already exists**, so importing **updates that existing profile** in place (vs. "Will import" = new candidate; "Duplicate → review" = same mobile, *different* email). Relabeled **"Will update existing"**, the preview now names the matched record (`↳ updates existing CV-000123 (same mobile & email)`) — the backend classifier now returns the matched CV for UPDATE rows too (display-only; import logic unchanged) — and a one-line legend explains all three outcomes.
- **Verified:** 331 backend tests (+regression: an imported city that is also an alias key resolves to its own master row); `check` clean; `tsc` + `vite build` clean. Reconcile/mapping APIs, bulk import, and Master Data CRUD unchanged.

## [Candidates] Fix: location reconciliation missed cities already in the master + drag-to-fill Add-Location
**Bug:** cities like "Gurugram" already present in Location Master still landed in **Unmapped locations** after import. **Root cause:** `_clean()` only `.strip()`-ed the imported text — no whitespace-collapsing and no Unicode normalization — so a trailing non-breaking space, doubled spaces, or full-width characters made `city.lower()` miss the cache key and fall through to "kept as text".
- **Normalized, case-insensitive matching.** New `_normalize_city()` applies **NFKC** → trim → collapse internal whitespace; matching is case-insensitive (`city__iexact` / normalized cache key). The alias map still applies (e.g. "Bengaluru" → "Bangalore").
- **Safe auto-map rules** (`_pick_unique_location`): the location cache is now **active-only** and indexes **all** rows per city. If the import carries **City + State (+ Country)** (comma-separated, e.g. "Gurugram, Haryana"), all supplied fields narrow the match. With **City only**, auto-map **only when exactly one** active record matches; if **multiple** same-named cities exist (different states), it is **left unmapped** for the admin to pick — never guessed. No match → kept as text as before. On a match the FK is set and `current_location_text` cleared, so it drops out of the unmapped list. `unmapped-locations` suggestions use the same rule (no ambiguous suggestions).
- **Drag-to-fill Add Location.** In the admin Add-Location modal the reference list is now **draggable**: drag an unmapped city onto the **City** field to populate it (the field stays fully editable to fix spelling before saving). Implemented with native HTML5 DnD via a generic, additive `dropTargetField` prop on `MasterCreateDialog` (drop **replaces** the value + refocuses; a highlight ring shows the target). State/Country/Status, validation, dedupe, and the existing create-then-map workflow are unchanged.
- **Untouched (per scope):** reconcile/mapping APIs, bulk import flow, Location Master CRUD, candidate-update logic. Backward compatible.
- **Verified:** 329 backend tests (+regression: normalize/whitespace/NBSP resolves, and a same-named city in another state stays unmapped until the state disambiguates); existing alias/unmapped/reconcile tests green; `tsc` + `vite build` clean; `check` clean. (Pre-existing unrelated flake `test_multiple_mobiles_uses_first_valid_with_warning` — a hardcoded mobile colliding with live dev-DB data — still fails independently of this change.)

## [Scale] Server-side pagination + searchable requirement pickers
Removes the client-side 100-row cap on the Requirements and Candidates lists (and the dropdowns that read them) that would hide records — and mismatch dashboard counts — once either list grew past 100.

**Lists are now truly server-driven** (the `DataTable` already supported a server mode; it's now used):
- **Requirements** — pagination, free-text search, and the dashboard/deep-link filters (`status=active` / a specific status code, `missing=recruiter` / `missing=hm`) are all applied **server-side** in `RequirementViewSet.get_queryset`, on top of the existing role scoping. So a KPI that reads "240 active" opens a list that pages through all 240, and the count matches. Search now also covers the **client name**. `RequirementsPage` seeds its search box from a `?q=` deep-link.
- **Candidates** — server pagination + search (name / mobile / email / company, plus the to-one **location** city & state). `CandidatesPage` pages server-side; the requirement filter is now a searchable picker. Skill-based finding is a **dedicated multi-select filter** (reusing `SkillMultiSelect`, `allowCreate={false}`) backed by a repeatable `?skill=<id>` param — multiple skills are **AND-ed** (candidate must have all selected), which a free-text join couldn't do without multiplying rows.

**Searchable, server-backed requirement pickers** replace every dropdown that previously read a capped list, so a requirement outside the newest 100 is now findable by typing its tracker, role, or client:
- New reusable `RequirementSelect` (async, debounced, role-scoped, keyboard-navigable) used in **Pipeline** (requirement selector), **Candidate form** ("tag to requirement"), **Bulk upload** ("add to review pool"), and the **Candidates** requirement filter.
- `TagToRequirementDialog` now searches **server-side** (its existing search box drives the query) instead of filtering a capped client list.

**Plumbing:** `useRequirements(params)` and `useCandidates(status, requirement, page, search)` now take pagination/search/filter params and use `keepPreviousData` for flicker-free paging; shared `useDebounced` hook extracted to `lib/`.

- **Verified:** 329 backend tests (325 → +3 server-side requirement filters/search, +1 candidate multi-skill AND filter); `check` clean; `tsc` + `vite build` clean.

## [Audit] Pre-deployment quality audit — security, reliability & UX fixes
A comprehensive review (auth/RBAC, workflow, DB integrity/concurrency, API validation, frontend state/UX). Genuine issues fixed; larger-scope items recorded as recommendations (see `docs/PRE_DEPLOY_RECOMMENDATIONS.md`).

**Security / authorization**
- **User directory locked to Admin.** `UserMasterViewSet` inherited the read-open reference-data policy, so any authenticated Recruiter/HM could `GET /api/users/` and harvest every user's email, mobile, username and role. Now `permission_classes = [IsAdministrator]`. The only non-admin user-picking flow (recruiter assignment) is itself Admin-only, so nothing legitimate depended on the open read. (+2 regression tests.)
- **Password policy now enforced.** `AUTH_PASSWORD_VALIDATORS` were configured but never invoked — `UserWriteSerializer` hashed any password (`"1"`, `"password"`) as-is. It now calls `validate_password` on create/update and surfaces failures on the `password` field. (+2 regression tests.)
- **Auth failures return 401, not 403.** `JWTAuthentication` defined no `authenticate_header`, so DRF downgraded every expired/invalid-token failure to 403. The frontend's axios interceptor only bounces to login on **401**, so an expired session left the user stuck on failing requests. Added `authenticate_header → "Bearer"`.
- **Login hardening.** Unknown usernames now run a constant-time dummy-hash comparison (closes a timing-based username-enumeration oracle) and failed/successful logins are logged via the `ats` logger (auth audit trail).

**Reliability / DB integrity**
- **Seat over-fill race.** Recording `JOINED` selected an open seat with no row lock, so two concurrent joins could both grab the same seat and double-fill a position. Now `select_for_update(skip_locked=True)` on the seat query inside `record_outcome`'s atomic block.
- **Rejection-count lost update.** `apply_application_outcome` incremented `active_rejection_count` via read-modify-write; concurrent rejections lost an increment and could bypass the Reject-Hold cool-off. Replaced with an atomic `F()+1` DB increment (row-locking) + re-read for the threshold.
- **Batch rollback made atomic.** `rollback_import_batch` soft-deleted candidates and flipped the batch status outside any transaction, and only `ROLLED_BACK` was guarded. Now `@transaction.atomic` with a precondition that the batch is `COMPLETED` (enforced in both the service and the view).
- **Reference-count fail-safe.** `_reference_details` swallowed count errors as `0` with no logging, which could let a still-referenced master row be hard-deleted. Now logs and fails safe (treats an uncountable relation as referenced).

**Frontend UX / correctness**
- **Dashboard "open requirement" deep-links.** A `?q=` link (from Needs-attention / Recent activity / Recent requirements) applied an invisible filter — no chip, no clear button, no count, and the misleading "No requirements yet." empty state. `describeFilter` now describes `q`, so the chip/clear/count and correct empty message render.
- **Consistent server error messages.** `RequirementFormDialog`, `AssignDialog`, `CandidateFormDialog`, `VerifyProfileDialog`, and `PositionsPanel`'s status-change handler ignored the error envelope (generic toast / wrong path). All now use `apiErrorMessage`, so the server's precise field/rule error is shown.
- **Dialog state bugs.** `AssignDialog` retained the last-picked recruiter after cancel → now resets on every close. `CorrectIdentityDialog` prefilled via a render-phase `setState` (fields snapped back when cleared) → moved to a `useEffect` keyed on the open review.
- **Misleading KPI drill-down removed.** The admin `joined_this_month` tile linked to an unrelated all-time `CLOSE_FILLED` requirement list; the drill-down is removed (no destination reproduces a this-month join count).
- **Verified:** 325 backend tests (321 → +4 security regressions); `check`, **NO DRIFT**, `spectacular` (0 errors); `tsc` + `vite build` clean.

## [Auth] Fix: wrong dashboard shown on first render after login (stale query cache)
**Bug:** immediately after login the app sometimes rendered another role's dashboard (e.g. a recruiter briefly saw the Admin dashboard); a manual browser refresh always corrected it. Reported as an init/state issue, not RBAC.
- **Root cause (traced login → auth → role → routing → render):** the TanStack Query `queryClient` is created once at module load ([main.tsx]) and lives for the whole tab — logging in/out never reloads the page, so its cache **persisted across users**. `useDashboard()` keys on a static `["dashboard"]` with no user identity, and `login()`/`logout()` never cleared the cache. So when a second user logged in on the same tab, `useDashboard()` returned the **previous user's cached dashboard on the first render** (TanStack serves cached data instantly, then background-refetches); `DashboardPage` chooses admin vs. operational from that response's `data.role`, so it painted the wrong dashboard until the refetch resolved. A hard refresh re-creates the `queryClient` (empty cache) → correct dashboard, which is exactly why refreshing "fixed" it and why it was intermittent.
- **Fix (proper, not a refresh workaround):** `AuthContext` now calls `queryClient.clear()` on **both** `login()` (before the new user's screens mount) and `logout()` (so the next login on the same tab starts clean). This purges *all* per-user, role-scoped cache — dashboard, requirements, candidates, pipeline, lookups — not just the dashboard, eliminating the cross-session bleed at its source. No query keys or component logic changed.
- **Verified:** `tsc --noEmit` clean; `vite build` clean. (The lone IDE "declared but never read" warning was stale — `queryClient` is used in both `login`/`logout`.)

## [Dashboard] Fix: "Candidates Available" showed 0 for recruiters
**Bug:** a recruiter's dashboard KPI **Candidates Available** read 0 even though the database held 48 recruitable (all NEW_CV) candidates. **Root cause:** the recruiter branch counted `CandidateMaster.objects.filter(uploaded_by=user)` — but in the seeded/reset baseline every candidate was uploaded by the reset actor (an admin), so no candidate was `uploaded_by` the recruiter. "Uploaded by me" was never the right definition of *available to me* anyway.
- **Fix (role-scoped, per the confirmed design):**
  - **Recruiter** — counts candidates genuinely available *to them*: distinct candidates with an **ACTIVE `candidate_requirement_review`** tag on one of the recruiter's assigned requirements, excluding `DB_DEFAULT_HIDDEN` statuses (Fake/Blacklisted/etc.). This is the recruiter's review pool — the candidates they can actually action.
  - **Admin** — added a global **Candidates Available** KPI = every recruitable candidate across the DB (all candidates minus `DB_DEFAULT_HIDDEN`), giving org-wide visibility.
- **Untouched (per scope):** all other KPIs, the pipeline/status widgets, and the recruiter candidate-upload list. Backend-only — the frontend renders the KPI array generically, so the admin tile appears with no UI change.
- **Verified:** 321 backend tests (+regression: recruiter KPI reflects the review pool, *not* uploads, and admin is a superset); `check`, `spectacular` (0 errors), **NO DRIFT**.

## [Candidates] UX: add locations without leaving Unmapped-Locations reconciliation (Admin)
Admins can now create a missing city **in place** during reconciliation instead of navigating to Master Data → Locations and back.
- **In-place modal (not navigation).** Evaluated both: the app already creates locations in-place elsewhere (`LocationSelect` → reusable `MasterCreateDialog`, which refreshes the location cache on save), so an in-place modal was feasible and clearly smoother — chosen over the navigate-away flow. An **"Add Location"** button (Admin-only) in the Unmapped Locations popup opens `MasterCreateDialog(configKey="locations")` layered over it; on save the new city is instantly available in the map-to dropdowns and a matching unmapped row is auto-selected. The mapping workflow is unchanged.
- **Add several without re-clicking.** `MasterCreateDialog` gained an opt-in `allowMultiple` "save & add another" mode (default off → existing callers keep create-then-close): after each create the dialog **stays open**, the form resets for the next city, and the footer shows a running "Added N: …" summary; **Done** closes. `useMasterForm` exposes a `reset()` to power it. The Unmapped popup enables this, so an admin adds all missing cities in one sitting, then maps.
- **Reference panel.** `MasterCreateDialog` gained an optional, additive `aside` slot; the Unmapped popup passes a **read-only** list of the current unmapped locations (e.g. "Chandigarh (2)") so the admin remembers what to add. It's contextual only — not a second mapping screen.
- **RBAC.** "Add Location" is gated to Admin (recruiters never see it); server-side `IsAdminOrReadOnly` on the locations endpoint still enforces it. Recruiters continue to map to existing locations only.
- **Untouched (per scope):** reconciliation logic, mapping behavior, bulk upload, Location Master CRUD, candidate-update logic. Purely a UX enhancement.
- **Verified:** `tsc` + `vite build` clean; `MasterCreateDialog`'s existing consumers unaffected (the `aside` prop is optional/backward-compatible).

## [Pipeline] Fix: scheduled screening type/time not shown on the board
**Bug:** the "Screening Scheduled" board column was blank even after scheduling a Video screening. **Root cause:** `schedule_screening` wrote the mode + time only to the `screening` table and advanced the stage, but never set the mapping's denormalized `screening_datetime` / `screening_mode` — which is exactly what the board column reads (and the column didn't render the mode at all).
- **Fix:** `schedule_screening` and `reschedule_screening_round` now mirror the round's mode + time onto the mapping; the board column shows **`<Mode> · <date-time>`** (e.g. "Video · Jul 24 20:00"). Migration **`0030`** (data-only, idempotent) backfills existing scheduled applications from their latest `SCHEDULED` round.
- **Verified:** screening suite green (+regression: scheduling sets the mapping's mode/time); `tsc` + `vite build` clean; `check`, **NO DRIFT**.

## [Requirements] Fix: "Required by" wrote the wrong date field (Created vs Target Close)
**Bug:** the requirement form's **"Required by"** input was bound to `req_date` (the requirement's creation date, shown as **"Created"**) instead of `target_fill_date` (shown as **"Target close"**). So a saved deadline appeared under *Created*, and *Target close* stayed blank. **Root cause:** frontend field mapping ([RequirementFormDialog] registered `req_date`) plus a display mapping where *Created* read the user-writable `req_date` rather than the system `created_on`.
- **Fix (traced FE→serializer→model→DB→back):**
  - Form: "Required by" now writes **`target_fill_date`**; `req_date` removed from the form entirely.
  - Serializer: `req_date` removed from `RequirementWriteSerializer` (no longer user-writable); `create_requirement` defaults `req_date` to the server date (DB column is NOT NULL).
  - Display: **"Created"** now reads the system **`created_on`** timestamp (Requirement details page + list column); **"Target close"** reads `target_fill_date`.
- **Result:** Created = system creation timestamp (never user-editable, never changes on edit); Target Close = the user's Required-by value; editing Required by updates only Target Close.
- **Follow-on: recruiter assignment was broken by the same bad data.** Rows created under the old bug had a *future* `req_date`; assigning sets `assigned_date = today`, violating `chk_dates (assigned_date >= req_date)` → "Could not assign the requirement." Migration **`0029`** (data-only, idempotent) resets a future/misplaced `req_date` to the true creation date and recovers a lost deadline into `target_fill_date`. New requirements were already safe.
- **Verified:** 320 backend tests (+regressions: Required-by→target_fill_date & Created immutable; assign a newly-created requirement succeeds); `tsc` + `vite build` clean; `check`, `spectacular` (0 errors), **NO DRIFT**.

## [Dev] Database Reset → seeded demo baseline (`manage.py reset_demo`)
A dev/test utility that restores the system to the clean **initial-state** baseline so a recruiter can test the full lifecycle from the start without recreating data.
- **Baseline produced:** 9 demo requirements **Open**, all positions **Open** (0 filled), 48 candidates at **New CV** with their **own** skills, 48 explicit **review-pool tags** (candidates under review, distributed by domain) — and **no** `jd_cv_mapping`, screenings, interviews, activity/communication logs, status history, outcomes, or closed requirements/positions.
- **Transactional-only (Option A):** master/reference data is preserved; the demo entities the baseline needs (clients, client-managers, users, skills, locations, domains) are ensured via `get_or_create` — created only if missing, never overwritten.
- **Mechanism:** one `TRUNCATE … RESTART IDENTITY` over the **15** transactional tables (FK-closed set — verified via live PostgreSQL that no master references a transactional table, so no `CASCADE`), then rebuild — all in one atomic transaction. **Idempotent.** No filesystem cleanup (the app stores no uploaded files — verified). Reuses `seed_demo`'s data definitions (single source of demo data).
- **Guarded:** refuses unless `DEBUG` is on or `ALLOW_DEMO_RESET=1`; interactive DB-name confirmation (or `--yes` for CI). Management command only — never exposed over HTTP.
- **Verified:** 318 backend tests (+5 reset: initial-state baseline, own-skills + tagged/no-mapping, masters preserved, idempotent, clear-empties-tables); `check`, `spectacular` (0 errors), **NO DRIFT**.

## [Pipeline] Explicit pre-pipeline Review Pool (candidate ↔ requirement "under review")
Separated **"under review for a requirement"** from **"entered the recruitment pipeline."** A new transactional table `candidate_requirement_review` (migration `0028`, additive) holds the explicit pre-pipeline association; `jd_cv_mapping` now means *only* "entered the pipeline (Shortlist)."
- **No more implicit skill association.** Selecting a requirement at manual/bulk create no longer copies the requirement's skills onto the candidate — it creates an explicit ACTIVE review tag. Candidate skills come solely from the candidate's own profile (manual entry / Verify & Update). `upsert_candidate`'s `requirement` param now tags for review instead of copying skills.
- **Review Pool = explicit tags only.** `new_cv_candidates_for_requirement` returns candidates with an ACTIVE tag for that requirement (skill overlap is now *ranking-only within* the tagged set, never membership).
- **Recruiter decisions** (`apply_candidate_decision`) each resolve the review; only **Shortlist** creates a `jd_cv_mapping`: Shortlist → mapping + resolve `SHORTLISTED` (+ candidate → Talent Pool); **Talent Pool** → resolve `TALENT_POOL` (no mapping); **Not Suitable** → resolve `NOT_SUITABLE` only (no mapping, global status unchanged — *changed*: previously created a closed mapping); **Fake/Blacklist** → global status + resolve **all** active reviews.
- **Multi-requirement** tagging: one ACTIVE row per `(candidate, requirement)` (`UNIQUE`), a candidate may be under review for many; shortlisting for one leaves the others active. **Requirement closure** (Close Lost / End Recruitment / Close Filled) sweeps that requirement's active reviews (`REQ_CLOSED`).
- **APIs:** `POST /candidates/{id}/tag-requirements/`, `POST /candidates/{id}/untag-requirement/`; candidate detail returns `active_reviews`. **Authorization (§9):** only the requirement's assigned recruiter (or an admin) may tag/untag; enforced on bulk/manual create too.
- **Frontend:** "Add to Review Pool" (repointed from instant-shortlist), bulk/manual relabelled to tagging (no skills), Verify & Update decisions unchanged (Talent Pool is its own button), candidate drawer shows "Under review for…" with Remove.
- **Verified:** 313 backend tests (+15 review-pool incl. tagging/no-skill-copy, pool-from-tags, all five decisions, multi-tag, closure sweep, auth, guards; 2 legacy tests updated); `check`, `spectacular` (0 errors), **NO DRIFT**; `tsc` + `vite build` clean.
- **Next:** the database reset / seed baseline will be built on this workflow (candidates `NEW_CV`, real skills, ACTIVE review tags for the 15/10/8 distribution, no mappings).

## [Requirements] Requirement closure frees remaining candidates to the Talent Pool
When a requirement reaches an **irreversible** terminal state, its remaining *active* applications are auto-closed with a system (non-rejection) outcome and the candidates return to the Talent Pool — so they're immediately available for future requirements. One reused write-path, `pipeline.services.close_remaining_applications(requirement, outcome, user)`, powers every scenario (wraps the existing `close_application` → sets `is_closed/closed_on/closed_by/latest_outcome`, AUTO audit row, timeline, and candidate automation).
- **Triggers & outcomes:** `CLOSE_FILLED` (auto, on the seat rollup when the last seat fills) → `REQ_CLOSE_FILLED`; `CLOSE_LOST` (manual HM) → `REQ_CLOSE_LOST`; **End Recruitment** on a partially-filled requirement → `REQ_POSITIONS_WITHDRAWN`. Three new `application_status_master` OUTCOME rows (migration `0026`, data-only/additive, NO DRIFT).
- **Terminal Partial Filled without a new status:** rather than add a `CLOSE_PARTIAL` status, a **permanent End Recruitment** decision is persisted on the requirement itself — new columns `recruitment_ended` / `recruitment_ended_on` / `recruitment_ended_by` (migration `0027`, additive/backward-compatible). See the dedicated entry below.

## [Requirements] End Recruitment — permanent business decision on an expired, partially-filled requirement
HM-only action (`POST /requirements/{id}/end-recruitment/`) for an **Expired + Partial Filled** requirement: permanently stop recruiting the remaining seats. It persists the decision on the requirement (`recruitment_ended` / `_on` / `_by`), withdraws the remaining **Open** seats to **Inactive** (new seat `status_source = AUTO_END_RECRUITMENT`; Filled/Held/Cancelled untouched), and closes every remaining active application via the shared `close_remaining_applications()` → `close_application()` path (outcome `REQ_POSITIONS_WITHDRAWN`, candidates returned to the Talent Pool, terminal apps skipped). Transactional and idempotent.
- **Rollup conflict resolved (the key design point):** inactivating the open seats would otherwise make the seat rollup compute `CLOSE_FILLED` (only the filled seat still counts). The `recruitment_ended` flag is the **source of truth** that freezes `recompute_requirement` — so the requirement keeps **status = Partial Filled**, **Expired = Yes**, **Recruitment Ended = True** (three distinct signals). Chosen over deriving the state from seat metadata (explicit + queryable + robust); the only cost is one additive, backward-compatible migration.
- **Permanent & guarded:** the flag blocks new candidate tagging / pipeline progression / seat activation even after the Target Fill Date is later extended (unlike the temporary Expired pause). The endpoint is HM-only (fixed a `get_permissions` gap that had let it fall through to any authenticated user). Cancelled requirements are unchanged (reopenable → no auto-close).
- **Reporting/audit:** `active_application_count` added to the requirement serializer (efficient filtered annotation) for the confirmation summary; withdrawn seats show as Inactive (distinct source) so Filled vs Withdrawn is clear; requirement/seat/application history + timelines all record the transitions.
- **Extend Target Fill Date (the temporary-Expiry counterpart):** an HM-only "Extend target fill date" action (reuses the requirement PATCH) is offered while a requirement is **Expired** (and not ended) — setting a future date clears the Expired overlay and resumes recruitment immediately, without touching seats or applications.
- **Finality:** once ended, the requirement is read-only and the decision is irreversible — no Extend, no status change, no edit (enforced in the UI *and* the backend `update`/`set-status` guards); the HM menu shows only View.
- **Frontend:** HM-only "End recruitment" action shown only for Expired + Partial Filled (not already ended), with a confirmation dialog summarising open seats withdrawn, active applications to be closed, and irreversibility; "Extend target fill date" dialog for expired requirements; the Expired banner/badge is replaced by a **Recruitment Ended** banner/badge on the details page.
- **Verified:** 299 backend tests (14 closure/end-recruitment incl. permissions, permanence across date-extension, seat inactivation, rollup-freeze, idempotency, read-only finality); `manage.py check`, `spectacular` (0 errors), **NO DRIFT**; `tsc` + `vite build` clean.
- **Cancelled is deliberately excluded** — it is reopenable (`CANCELLED → OPEN`), so closing its applications would destroy the pipeline a reopen must restore.
- **Safety:** idempotent (already-closed apps skipped; a second End Recruitment closes 0); the seat-winning (Joined / in-flight join) application is excluded so the fill that triggers `CLOSE_FILLED` is never clobbered; already-terminal outcomes (Joined/Rejected/…) untouched; an active **Reject-Hold** cool-off is never silently released. Fully transactional and audited (AUTO).
- **Frontend:** HM-only "End recruitment" row action shown only for an expired, partially-filled requirement; badge labels for the new outcomes.
- **Verified:** 295 backend tests (+10 covering Close Lost / Close Filled-on-join / End Recruitment pre-conditions + idempotency / Cancel-no-op / Reject-Hold preserved / audit); `manage.py check`, `spectacular` (0 errors), NO DRIFT; `tsc` + `vite build` clean.

## [Candidates] Bulk Upload redesigned around the mentor-approved Naukri template
Rebuilt the bulk-upload module to use the mentor's Naukri "Candidate Details" export as the single source of truth. Full mapping in [docs/BULK_UPLOAD.md](BULK_UPLOAD.md).
- **Parser** (`candidates/services.py`) — selects the "Candidate Details" sheet, **auto-detects the header row** (not row 1), ignores the "Candidate insights" sheet + blank/decorative rows; label-based column map; value parsers for experience (`7Y 7 M`→7.6), salary (`INR 7.2 L`→7.2; USD/`0.0 L`→blank), age+DOB (`32 y (09 Sep 1993)`→ age snapshot + DOB), highest qualification (Post-PG>PG>UG), and multi-number mobile cells (first valid + warning). Collects **all** errors per row with the real Excel row number.
- **Location** — curated alias map (Bengaluru→Bangalore, …), **no auto-create**; unmapped cities preserved in new `current_location_text` + a row-level warning (never discarded). Preferred-location: first → FK, rest → notes. Resume Title + Comments 1–5 → notes.
- **DB (migration `0024`, additive/nullable)** — `date_of_birth`, `age_at_import` (import snapshot; never recalculated), `postal_address`, `current_location_text`. No existing columns changed; NO DRIFT.
- **Endpoints** — `bulk-preview` (validate-only, no writes → per-row status/errors/warnings), `bulk-upload` (imports **valid rows only**; invalid rows never block valid ones; possible duplicates → existing Admin review queue, duplicate detection unchanged; optional `requirement` + configurable `source` defaulting to "Naukri" via Source Master), regenerated sample template.
- **Frontend** — redesigned `BulkUploadDialog`: download template, upload, source/requirement selectors, **Validation Summary + Import Preview** (valid + invalid with row numbers/reasons + warnings), **Import valid-only**, and **Download report** (CSV). DOB/Age (as imported)/Address surfaced read-only in the Candidate Drawer.
- **Preserved unchanged:** duplicate detection, candidate verification, pipeline, screening, communication, and workflow logic.
- **Verified** — 240 backend tests (19 new: parsing, header auto-detect, value parsers, alias hit, unmapped-location preservation, preferred→notes, multi-number, required/email/mobile, in-file duplicate, valid-not-blocked, update vs review-routing, source, preview-no-write); live `bulk-preview` on the real mentor file → 40/40 valid, 0 writes; `manage.py check` + `spectacular` clean; NO DRIFT; `tsc` + `vite build` clean.

## [Bulk Upload] Feature 1 — email duplicate validation
- In-file duplicate emails and emails already owned by a **different** candidate are now caught during validation (preview + import) as clean `INVALID` rows (with the conflicting CV serial) instead of failing on the DB `UNIQUE(email)` constraint. Mobile stays the identity key; `detect_duplicate` is unchanged. `upsert_candidate`'s `IntegrityError` retry is narrowed to genuine cv_serial collisions. No schema change. Tests: +5.

## [Bulk Upload] Interrupted-import progress persistence
- `_execute_import` now records `total_rows` **before** the loop and checkpoints the running counts (created / updated / duplicate / skipped) every `BULK_PROGRESS_FLUSH_EVERY` rows (default 50), and on a Python-exception failure. So an import interrupted by a crash/kill reports **accurate progress** in History (to within the flush interval) instead of showing 0 until completion.
- Lightweight: ~1 extra UPDATE per 50 rows (negligible vs the per-row upserts). Partial-success and rollback are unchanged (they key off per-row commits / the `import_batch` FK, not the counts). No schema change (reuses existing count columns); per-row detail (`row_report`) is still written only at completion.
- Note: `skipped_count` covers both validation-invalid and runtime-error rows; a dedicated `failed_count` was intentionally NOT added (would be an unrequested schema change) — the completed `row_report` distinguishes INVALID vs ERROR per row.
- Verified: 285 backend tests (+2: progress persisted on interruption, periodic checkpoint), `manage.py check`, NO DRIFT.

## [Bulk Upload] Feature 5a — preview draft → import confirm
- **Preview now persists a reusable DRAFT batch** (per-row serialized payloads in `row_report`) and returns its `batch_id`. **Import confirms that draft by id** (`POST /candidates/bulk-upload/` with `batch_id`) — importing the *exact* validated dataset with **no re-upload and no re-parse**. The legacy direct-`file` import path is kept as a fallback. A shared `_execute_import` loop powers both, so behavior is identical.
- **Same-dataset guarantee, DB still authoritative:** confirm reconstructs candidate kwargs from the draft (FK ids → objects, ISO → date) and runs the per-row upsert, so a row that became a duplicate *between* preview and confirm is still handled correctly (verified).
- **Concurrency / double-confirm:** DRAFT→PENDING is an **atomic conditional claim** (`filter(status=DRAFT).update(PENDING)`) — a second/concurrent confirm finds 0 rows and is rejected, so a draft can never import twice. Confirm is intentionally **not** wrapped in a single transaction (preserves partial-success + FAILED-marking).
- **Lifecycle:** re-previewing the same file supersedes the prior draft; DRAFT batches older than `BULK_DRAFT_TTL_HOURS` (24h) are purged by the daily maintenance job; drafts are excluded from Import History.
- Frontend confirms via `batch_id`; a stale/expired draft surfaces the exact backend message ("re-run the preview").
- **5d (admin-editable alias master) deferred** — the code-based `_CITY_ALIASES` stays until there's an operational need.
- Verified: 277 backend tests (+8), `manage.py check`, NO DRIFT, `spectacular` 0 errors, `tsc` + `vite build` clean.

## [Bulk Upload] Feature 5 (partial) — validation polish
Four small, additive hardening items (no schema, backward compatible):
- **5b Truncation warnings** — Candidate Name / Current Employer / Designation now warn when truncated to their column length (previously silent; only postal address warned).
- **5c Header-variant coverage** — `_HEADER_MAP` extended with common real-world spellings (**Mobile Number**, Phone Number, E-mail, Full Name, Current Salary, Job Title, Graduation, …). Deterministic only (no fuzzy matching, to avoid mis-mapping columns like "alternate email").
- **5e Duplicate-file warning** — preview + import flag (non-blocking) when the exact file bytes (SHA-256) were already imported in a prior COMPLETED batch; the dialog shows "already imported (batch #N)".
- **5f DOB sanity** — a future or implausible (age <14 or >100) Date of Birth is dropped with a warning; an Age↔DOB mismatch >2 years is flagged (both kept as imported). The `age_at_import` snapshot is never recalculated.
- Also hardened parsing generally: an unreadable/corrupt file → clean 400 (`BulkParseError`), and the dialog surfaces exact backend messages.
- **Deferred (need design sign-off):** 5a (preview→import draft-token flow — API/contract change) and 5d (admin-editable alias master — new table + admin CRUD).
- Verified: 269 backend tests (+4), `manage.py check`, NO DRIFT, `spectacular` 0 errors, `tsc` + `vite build` clean.

## [Bulk Upload] Feature 4 — performance (N+1) + limits
- **Killed the N+1s** in preview/import: locations resolve against a one-time `_location_cache()` (no per-row query), and duplicate/email classification runs in-memory against `_build_existing_index(parsed)` — two **bounded** queries scoped to the file's mobiles/emails instead of ~2 DB lookups per row. `_classify_row(p, index)` mirrors `detect_duplicate`'s rules exactly; the DB unique constraints + `upsert_candidate` remain the authoritative write path.
- **Limits:** file-size cap (`BULK_MAX_BYTES`, default 5 MB) rejected before parsing in the view; row cap (`BULK_MAX_ROWS`, default 5000) parses one row past the limit then rejects with a clear message — both settings-overridable.
- Per-row upsert/transaction and partial-success behavior are unchanged. No schema change.
- **Hardening (production review):** a corrupt / empty / non-xlsx-content / password-protected file now returns a clean `BulkParseError` → 400 (previously an unhandled 500); the Bulk Upload dialog surfaces the **exact** backend message (e.g. "File too large (max 5 MB).") via `apiErrorMessage` instead of a generic toast. Verified: 265 backend tests, `manage.py check`, NO DRIFT, `spectacular` 0 errors, `tsc` + `vite build` clean.

## [Bulk Upload] Feature 3 — location reconciliation workflow
- Closes the loop on import locations "kept as text" (`current_location_text`, FK NULL). **No new schema** — uses the existing column + Location Master.
- **API:** `GET /api/candidates/unmapped-locations/` (distinct unmapped texts + candidate counts + a suggested master match via the alias map) and `POST /api/candidates/reconcile-location/` `{text, location_id}` (bulk-links every still-unmapped candidate with that exact text → sets the FK, clears the text). Recruiter/Admin. **Never auto-creates** a Location Master row — add the city via Master Data first, then map.
- **Verify & Update** now auto-clears `current_location_text` once a real Location is set, so a candidate stops showing as unmapped.
- **Frontend:** an admin/recruiter **Unmapped locations** dialog (per-text counts, suggested city pre-selected, map-to-city); the Candidate drawer flags an unmapped imported location. Reconcile only ever touches FK-NULL rows (never overrides a manual location).
- Verified: 259 backend tests (+4), `manage.py check`, NO DRIFT, `spectacular` 0 errors, `tsc` + `vite build` clean. No change to import, duplicate detection, pipeline, screening, or communication.

## [Bulk Upload] Feature 2 — import batch tracking, audit & history
- Each upload is now recorded in a new **`bulk_import_batch`** table (uploader, file name + SHA-256 hash, source/requirement, counts, status, full per-row `row_report` jsonb). Created candidates carry a nullable **`candidate_master.import_batch_id`** FK (NULL for manual creates / bulk updates). Migration `0025` (additive; NO DRIFT).
- **API:** `GET /api/import-batches/` (recruiter → own, admin → all), `GET /api/import-batches/{id}/` (detail + report), `GET …/report/` (re-downloadable .xlsx), `POST …/rollback/`. Candidate **list** now filters `is_active=True` (rolled-back rows drop out; detail stays reachable by id).
- **Rollback** = soft-delete (`is_active=False`) of only the candidates a batch **created** that are still untouched (status `NEW_CV`, not in any pipeline); worked/updated candidates are kept; batch marked `ROLLED_BACK`. Allowed for the uploader or an admin.
- **Frontend:** an **Import history** dialog on the Candidates page (per-batch counts/status, download report, roll back).
- **Resilience:** an unexpected in-process failure marks the batch **FAILED** (never left PENDING) and re-raises; a recovery sweep (`fail_stale_import_batches`, wired into the daily lifecycle job) marks batches stuck PENDING > 30 min as FAILED; admins can also `POST …/mark-failed/` a stuck batch. Rollback reverses **only created** candidates — updated ones are never reversed and are reported via `updated_not_reversed`. `file_hash` is stored for a future duplicate-upload warning (not yet surfaced).
- Existing import behavior, duplicate detection, verification, pipeline, screening, and communication are unchanged. Verified: 255 backend tests, `manage.py check`, NO DRIFT, `spectacular` 0 errors, `tsc` + `vite build` clean.

## [Pipeline] Workflow cleanup — stage actions, interviewer validation, Communication tab, terminology
Seven aligned changes across pipeline UI + engine (diagram is the source of truth).
- **JD Email Sent** — removed the **No Response** outcome (engine + UI); the stage now offers only **Schedule Screening** and **Drop**.
- **Schedule Screening dialog** — **Interviewer is now mandatory**, letters/spaces only (digits/symbols blocked on input), stored **Title Case**. Enforced in the UI (input sanitize + disabled submit) and server-side in `ScreeningScheduleInputSerializer.validate_interviewer`.
- **OK to Proceed** — removed **Blacklisted** from the outcome menu (engine + UI); keeps Release Offer / Reject / Drop / Mark Fake.
- **Communication tab** — replaced the flat JD-email log with a list of **all pipeline candidates for the requirement + their latest status**; selecting one opens a **read-only Activity Timeline drawer** (scoped to that candidate + requirement; includes JD-email events). No resume/verify/update/status actions. New `CommunicationsPanel.tsx`.
- **Verify badge** — in the pipeline, the per-row Verify action is now a **non-clickable "Verified" badge**; verification/profile edits are only possible **before** entering the pipeline (the "Candidates to review" pool). Removed the pipeline-row Verify dialog wiring.
- **Screening bug fix** — scheduling from JD Email Sent now **advances to Screening Scheduled and closes the dialog**; the Record Outcome + Reschedule controls render **only** when the mapping is in the Screening Scheduled stage (`canManage`), so the outcome form no longer appears in the JD Email Sent context.
- **Terminology** — single source of truth `lib/workflow.ts` (`ACTION_LABEL`/`actionLabel`): **actions are verbs** (Shortlist, Send JD, Schedule Screening, Reschedule, Reject, Drop, Blacklist, Mark Fake, Release Offer, Withdraw, Mark Joined); **statuses/badges/timeline** use backend state names (Shortlisted, Rejected, Dropped, Blacklisted, …). Applied across the pipeline board + screening popup.
- **Verified** — 41 pipeline/screening tests (3 new: No-Response invalid at JD Email Sent, Blacklist invalid at OK to Proceed, interviewer required/alpha/Title-Case); `manage.py check` clean; `spectacular` 0 errors; frontend `tsc` + `vite build` clean. (One unrelated lifecycle test fails against seed demo data + the current clock — a JOINED demo candidate lands in the 24-month window; not caused by these changes.)

## [Pipeline] Screening popup records the application outcome
Consolidated all Screening-Scheduled outcome handling into the Screenings popup.
- **Removed the standalone Outcome dropdown** from the Screening-Scheduled pipeline row — the row now shows only **Screenings** (+ Verify). Clicking Screenings opens the popup as before.
- **Popup "Record Outcome"** now sets the **application** outcome (was screening-round outcomes Passed/Failed/No Show/Cancelled/Reschedule Required): **OK to Proceed** (advances → OK to Proceed, engine outcome `PASSED`), **No Response**, **Dropped**, **Rejected**, **Fake**, **Blacklisted** (close). Routes through the engine (`POST /pipeline/outcome/` → `record_outcome`), so `latest_outcome_id` and the Stage/Outcome architecture stay intact; non-hired closes keep the opt-in Talent-Pool prompt.
- **Reschedule** stays as the separate action at the top of the popup and is intentionally not in the outcome dropdown. No other pipeline stage changed.
- **Verified** — live end-to-end confirms popup "OK to Proceed" advances the stage (200, `latest_outcome=PASSED`); `tsc` + `vite build` clean. Backend unchanged (endpoint + `STAGE_OUTCOMES` already supported all six); prior 218 tests hold.

## [Pipeline] Stage-aware outcome menus — Screening Scheduled & OK to Proceed
Aligned the per-stage Outcome dropdowns with the agreed process so each stage only offers outcomes valid there (Stage/Outcome architecture unchanged — `application_status_master.kind` + `latest_outcome_id`).
- **Screening Scheduled** — the menu now manages the interview only: **Reschedule** (opens the Screenings tab), **No Response**, **Dropped**, **Reject**, **Fake**, **Blacklist**. The manual "OK to Proceed" was removed; advancing to OK to Proceed now happens by **recording the interview as _Passed_ in the Screenings tab**, which routes through the centralized engine (`complete_screening` → `record_outcome(PASSED)`). Rescheduling remains available in the Screenings tab (round-level).
- **OK to Proceed** — menu now offers **Release Offer** (advance) plus **Rejected**, **Dropped**, **Fake**, **Blacklist** (close). Previously only Release Offer + Reject.
- **JD Email Sent** — added **Dropped** as a valid outcome (a candidate can drop out after receiving the JD); the board already surfaced "Drop" here but the engine previously rejected it. Now closes cleanly via `record_outcome(DROPPED)`.
- Backend `STAGE_OUTCOMES` already permitted the Screening/OK-to-Proceed combinations, so validity there is unchanged; the fix is the context-aware UI plus the pass-advances-stage wiring (and the JD-Email-Sent Dropped addition). Fake/Blacklist stay hard dispositions (no Talent-Pool prompt); No Response / Dropped / Rejected keep the opt-in Talent-Pool prompt.
- **Verified** — 218 backend tests (new: passing a screening advances to OK to Proceed; failing does not; Drop closes from JD Email Sent); running-server end-to-end confirms schedule → Passed → OK to Proceed; `tsc` + `vite build` clean; `manage.py check` clean.

## [Pipeline] Screening — round-level reschedule, strict future time, single Video round
Refinements to the screening scheduler in response to real recruiter use.
- **Strict future date *and* time** — the picker's `min` is recomputed on every render (not once at mount) and the submit guard compares against `Date.now()` at click-time, so a time earlier *today* can no longer be chosen. The backend (`schedule_screening` / new `reschedule_screening_round`) enforces `> now` as the authority.
- **Reschedule facility** — a still-**Scheduled** round can be moved to a new future time. New service `reschedule_screening_round` (`pipeline/screening.py`) + `POST /pipeline/screenings/{id}/reschedule/` + a **Reschedule** control on the open round in the screening dialog. Writes a timeline note; a completed round is not reschedulable.
- **Single Video round (migration `0023`)** — Telephonic mode **deactivated** (row kept, not deleted) so it no longer appears in the scheduling dropdown (lookups already filter `is_active`). The Video→Telephonic prerequisite is now **conditional on Telephonic being active**, so Video schedules directly today and re-activating Telephonic automatically restores the gate — extensible for future rounds with no code change.
- **Timezone bug fixed (was: "Could not schedule the screening")** — the project runs `USE_TZ = False` on an IST server, so `timezone.now()` is local wall-clock but the client sends instants as UTC (`Date.toISOString()`), which DRF parses to naive **UTC**. Comparing/storing that against local `now()` was off by the server's UTC offset, wrongly rejecting any time less than ~5.5 h ahead. New `core.timeutils.to_local_naive` normalizes an incoming datetime to the app's naive-local convention; applied at every screening write-path (`schedule_screening`, `reschedule_screening_round`, `advance_stage`, `reschedule_screening`). Stored times now round-trip correctly for display.
- **Error messages surfaced** — the API wraps errors as `{ error: { detail } }`, but several toasts read `data.detail` (always undefined → generic fallback). New shared `lib/apiError.ts` unwraps the envelope; wired into the screening dialog, stage board, requirement status, positions, and tag-to-requirement flows so real backend messages show.
- **Verified** — 215 backend tests (reschedule guards, telephonic-active/inactive gate, past-time rejection, **near-future UTC accepted**); running-server curl confirms a 20-min-ahead UTC payload now returns 201 (was 400); `tsc` + `vite build` clean; `spectacular` 0 errors; **NO schema drift**; reference seed marks Telephonic inactive for fresh DBs.

## [Pipeline] Stage × Outcome model + Verify-&-Update decision (Candidate = master repo)
Recruitment redesign: **Stage** (where a candidate is) and **Outcome** (what happened) are now independent, and the recruiter's single **Verify & Update** decision replaces the standalone Review.
- **Stage vs Outcome (migrations `0021`/`0022`)** — `application_status_master` gains **`kind`** (`STAGE`/`OUTCOME`) + `sort_order`; new outcomes **Blacklisted, Offer Accepted, Passed, Fake**. `jd_cv_mapping.application_stage` is now stage-only; new **`latest_outcome`**, **`is_closed`**, **`closed_on`**, **`closed_by`**. Existing closed rows backfilled (outcome → latest_outcome, stage → prior stage). Additive; no schema revisited.
- **Centralized engine** (`pipeline/services.py`) — one write-path: `record_outcome` (validates the stage×outcome machine; advances or closes), `advance_stage` (Send JD / Schedule Screening / Release Offer), `reschedule_screening` (future-datetime enforced), `enter_pipeline` / `close_application`. Flow: Shortlisted → JD Sent → Screening Scheduled → OK to Proceed → Offer Released → Awaiting Joining, with per-stage outcomes (No Response, Passed, Rejected, Dropped, Fake, Blacklist, Offer Accepted/Declined, Joined, Withdrawn). Legacy `transition_mappings` kept as a thin back-compat router. Full audit to `status_change_history` (`APPLICATION`) + candidate timeline.
- **Verify & Update decision** — `POST /candidates/{id}/verify-profile/` now takes one **decision** (Shortlist / Not Suitable / Fake / Blacklist / Save to Talent Pool); only Shortlist enters the pipeline. Standalone Review retired (endpoint kept for back-compat).
- **Talent Pool is opt-in** — a non-hired close (Not Suitable, Rejected, Dropped, No Response, Offer Declined, Withdrawn) records the original outcome and prompts **"Move candidate to Talent Pool?"**; the candidate moves to Talent Pool only on **Yes**. Reject-Hold (2nd rejection) and Joined stay automatic; Fake/Blacklist set the global disposition.
- **APIs** — new `pipeline/outcome/`, `pipeline/advance/`, `pipeline/reschedule/`, and `pipeline/mappings/{id}/timeline/` (per-requirement timeline). Mapping serializer now returns current stage, latest outcome, is_closed, recruiter.
- **Frontend** — pipeline board shows **Latest Outcome · Recruiter · Last Updated** + a per-row **Verify & Update** action; verify dialog carries the five decisions + the Talent-Pool prompt; screening picker blocks past date/times (schedule + reschedule).
- **Verified** — 209 backend tests (engine advance/close, invalid-stage rejection, closed-immutable, future-datetime, Join fills seat, verify decisions, TP opt-in, endpoints, timeline); `tsc` + `vite build` clean; `spectacular` 0 errors; **NO schema drift** (32 models); schema + reference seed + `seed_demo` validated on a fresh DB (stage/outcome/closed correct).

## [Requirements/Positions] Two-workflow model — requirement↔position cascade, audit, expiry overlay
Requirement and Position lifecycles remain independently manageable but now **synchronize where the business rules require it**. Migration `0020` (additive).
- **New system-managed position status `Inactive`** — set ONLY by the requirement cascade (never a manual choice). Put a requirement on **Hold** or **Cancel/Close-Lost** → its **Open** seats become **Inactive**; **Filled** seats and manually **Held/Cancelled** seats are untouched (Rules 4/6/8). **Resume** reopens only Hold-inactivated seats; **reopen a Cancelled** requirement reopens all system-inactivated seats and always returns to Open (Rules 5/7). A new `requirement_position.status_source` (`MANUAL` / `AUTO_REQ_HOLD` / `AUTO_REQ_CANCEL`) drives this and prevents manual cancels/holds from being auto-reopened (Rule 12).
- **Cancelled vs Closed Lost are explicit HM actions with a mandatory reason** (never auto-derived from seat cancellations). **Cancelled can be reopened; Closed Lost is terminal.** Hold also requires a reason (Resume / manual position changes: reason optional).
- **Add / delete positions** — HM/Admin can add seats to an **active** requirement (New/Assigned/Open/Partially Filled); new seats are Open and the rollup reflects the added demand. Adding is blocked on Filled/Cancelled/Closed-Lost/Expired. Delete is allowed only for a never-Filled seat with no activity (else Cancel).
- **Expired overlay** — `Expired` is **removed as a stored status**; it is a derived, read-only overlay when the Target Fill Date passes and the requirement is non-terminal. While expired: recruiter pipeline actions, position changes, and add-positions are blocked; only the Target Fill Date is editable (extending it clears the overlay).
- **Recruiter guard** — pipeline actions (review / send-JD / transition / screening) are blocked while a requirement is on Hold, Cancelled, Closed Lost, or Expired.
- **Unified audit** — new `status_change_history` table records every requirement/position change (previous→new, reason, MANUAL/AUTO, changed_by/on); surfaced on the requirement **History** tab.
- **Permissions** — Hold/Cancel/Close-Lost/Resume and manual position status = **HM only** (Admins excluded); add positions = **HM + Admin**; recruiters cannot change requirement or position workflow.
- **UI** — requirement details show the Expired badge/message and a seat breakdown (Total / Open / Filled / Held / Cancelled / Inactive), an **Add positions** action, per-seat delete, and the status-history timeline.
- **Verified** — 192 backend tests (9 new: cascade, selective reopen, add/delete guards, manual-Inactive rejection, expiry read-only, recruiter block, audit); `tsc` + `vite build` clean; `spectacular` no errors; **NO schema drift** (32 models); schema + reference seed + `seed_demo` validated on a fresh DB.

## [Database] Schema sync + single official seeding process (no app changes)
Brought the repo's SQL into sync with the live PostgreSQL database and prepared it for collaboration. No application logic changed; `database/migrations/*` untouched.
- **`database/ats db schema.sql`** regenerated from the live DB (pg_dump `--schema-only -n ats`, normalized to keep `SET search_path = ats, public;`): all 31 tables, columns, PKs, FKs, checks, uniques, indexes, sequences/defaults. Verified **column-signature-identical** to the live schema (rebuilt on a throwaway DB and diffed).
- **`backend/check_schema_drift.py`** added as a permanent developer utility: compares every `managed = False` model to the live schema (missing tables/columns, type mismatches, missing FKs/indexes). Current result: **NO DRIFT** (31 models ↔ 31 tables). Documented in `database/README.md`.
- **Seeding consolidated.** `manage.py seed_demo` alone is **not** self-sufficient on an empty DB (it looks up lookup/enum rows it doesn't create). The stale `ats insert data 2.sql` (which inserted into dropped tables `cv_status_master`/`interview_round_master`) was **regenerated from live data** to hold **only** reference/master lookup data (roles, statuses, priorities, notice periods, req types, work modes, sources, screening modes, rejection reasons, JD email template) — idempotent (`ON CONFLICT DO NOTHING`), no transactional/demo rows. The **one official process** is now: apply `ats db schema.sql` → apply `ats insert data 2.sql` → `manage.py seed_demo`. Verified end-to-end on a fresh DB (48 candidates / 9 requirements seeded, no errors).
- **`database/README.md`** rewritten: PostgreSQL prereqs, create `ats_db`, apply schema, load reference data, configure `.env`, install deps, run backend + frontend, run the drift checker, and a troubleshooting table.
- **Verified** — schema identical to live; models match (no drift); `database/migrations` unchanged; 183 backend tests pass; `manage.py check` clean.

## [Candidates] Requirement filter for all roles (deterministic "mapped-only")
The Candidates **Requirement filter** is now available to **Admins, Recruiters and Hiring Managers** (previously HM-only).
- **Role-scoped list** (existing `GET /api/requirements/`): Admin → all; Recruiter → assigned; HM → owned.
- **Deterministic behaviour** — selecting a requirement shows **ONLY candidates mapped to it** (no auto-included New CV / Talent Pool). All mapped candidates show regardless of status (they're already associated); a status filter still composes on top. A candidate mapped to several requirements appears under each. Counts reflect only the mapped set.
- **Backend** — `?requirement=<id>` in `CandidateViewSet.get_queryset` now applies to **all roles**, gated by `_requirement_accessible` (Admin any / Recruiter assigned / HM owned); an inaccessible id returns **no rows** (no data leak). HM base visibility (New CV + Talent Pool + own-req mapped) still governs the *unfiltered* view and all detail actions.
- **Composes** with the unified search (name/mobile/email/skills/location), status filter, sorting, pagination and bulk actions.
- **Verified** — 183 backend tests (mapped-only for HM/REC/ADM; inaccessible → empty; recruiter scope; admin any + multi-mapping); `tsc` + `vite build` clean; `manage.py check` clean.

## [Candidates] Hiring Manager read-only sourcing access (permission + filter only)
Hiring Managers can now open the **Candidates** module in a **read-only** sourcing view. No recruitment business logic changed — this is a visibility/permission + filter enhancement.
- **Visibility (backend `CandidateViewSet.get_queryset`)** — an HM sees candidates whose global status is **New CV** or **Talent Pool**, PLUS any candidate **mapped to a requirement they own** (at *any* pipeline stage). They never see candidates that belong only to other HMs'/recruiters' requirements. Enforced on **every** action (list *and* detail → 404 by id otherwise).
- **Requirement filter (`?requirement=<id>`, HM-only)** — narrows to one of the HM's own requirements. *(Superseded by the "Requirement filter for all roles" entry above: selecting a requirement now shows ONLY candidates mapped to it, for every role.)*
- **Read-only** — HM was already blocked from every write action (`create/update/destroy/bulk_upload/set_status/clear_status/verify_profile` → REC/ADM only) and the pipeline `review`/tag endpoint (REC/ADM only). The UI hides all of these for HM (no Add/Bulk-upload/Change-status/Tag/Verify buttons); the drawer is view-only.
- **UI** — Candidates added to the HM sidebar; HM-only Requirement dropdown (their requirements only) + trimmed status filter (All visible / New CV / Talent Pool). **Recruiters and admins see no UI or behaviour change** (the requirement list is fetched only for HM).
- **Unchanged** — candidate lifecycle, application/pipeline statuses, duplicate detection, rejection counter/history, profile verification, dashboards, résumé storage, and all recruiter/admin workflows.
- **Verified** — 180 backend tests (5 new: HM sees New CV/Talent Pool; hidden candidate of another owner invisible incl. 404 by id; hidden candidate mapped to HM's own req visible; requirement filter scoping + unauthorised-id ignored; HM tag → 403); `tsc` + `vite build` clean; `manage.py check` clean.

## [Candidates] Drawer & search UX refinements (UI only)
Usability improvements to Candidate Management — no change to business logic, APIs, permissions, lifecycle, or duplicate detection.
- **Unified search** — the separate **Skills** filter dropdown was removed; the Candidates search box now matches **name, email, mobile, skills AND location (city + state)** in one field (case-insensitive, partial — e.g. "Mumbai", "Maharashtra", "Python", "Sneha"). Composes with the HM Requirement filter (which narrows the rows server-side first). Implemented client-side via a new opt-in `globalFilterFn` prop on the shared `DataTable` (default behaviour of other tables unchanged).
- **Drawer simplified** — the **Résumé** section (preview + "Download résumé") was removed from the Candidate Details drawer. Résumé upload/storage and the backend `GET /candidates/{id}/resume/` endpoint are untouched (only the drawer UI changed).
- **Tag to Requirement** — new drawer action (REC/ADM) opens a searchable requirement picker (search by requirement ID or title). Only shows requirements the recruiter is authorised to see (role-scoped list) and hides closed/cancelled/filled ones; already-tagged requirements are shown as **Tagged** and can't be re-added. Reuses the existing `POST /api/pipeline/review/` (Shortlist) mapping service — no new backend logic. On success the drawer's requirement history refreshes live (added `candidate-detail` invalidation to `useReviewCandidate`).
- **Verified** — `tsc` + `vite build` clean.

## [Candidates] Verify & Update Profile (single master profile, audited)
Recruiters can verify + update a candidate's **master** profile (typically during the screening call) — one record, reflected across every requirement (no per-requirement copies).
- **New endpoint** `POST /api/candidates/{id}/verify-profile/` (REC/ADM; **HM read-only → 403**). Edits non-system fields only (identity, experience, company/designation, notice, work mode, CTC, education, skills, certifications, notes); system fields (cv_id, serial, created_*, lifecycle status, audit) are not editable.
- **Verification stamp** — sets `profile_verified` + `profile_verified_by` + `profile_verified_on` (migration `0019` adds these, plus `current_designation`, `relevant_exp`, `certifications`, `additional_notes`).
- **Field-level audit (mandatory)** — new `candidate_profile_audit` table: one **append-only** row per changed field (`field_name, old_value, new_value, source="Recruiter Manual Update", changed_by, changed_on`). History is never overwritten.
- **Timeline** — each update logs a `CandidateInteraction` summarising who/when + which fields changed (shows in the candidate drawer).
- **Duplicate detection reused** — changing mobile/email re-checks against other candidates; a collision opens a **Possible Duplicate review** (existing workflow, via `record_possible_duplicate`) and the edit is **not saved** (`409`). No separate duplicate logic.
- **UI** — "Verify & Update Profile" dialog in the candidate drawer (prefilled from the master profile) with a "Mark verified" checkbox; success toast: *"Candidate profile updated successfully. Changes will be reflected across all requirements."* Drawer header shows the verification stamp.
- **Backward-compatible** — reuses existing models/serializers/services; no change to lifecycle, statuses, pipeline stages, requirement mapping, duplicate-review workflow, rejection counter, or dashboard.
- **Verified** — 175 backend tests (update + field audit; append-only history; verification stamp; mobile/email conflict → review + not saved; HM 403); `tsc` + `vite build` clean; `spectacular` 0 errors; `seed_demo` idempotent.

## [Candidates] Bulk upload feeds the Duplicate Review queue
Bulk-upload possible-duplicates (same mobile / different email) now **persist to the Admin Pending Duplicate Review queue** (and the dashboard "Possible duplicates to review" count), not just the batch report.
- New shared service `record_possible_duplicate(...)` (create + dedupe on `existing_candidate + new_mobile + new_email` among PENDING) — used by **both** bulk upload and the single-create escalation (`DuplicateReviewViewSet.create` refactored to call it; behaviour unchanged, still 201 new / 200 existing).
- `import_candidates_excel` calls it on every `POSSIBLE_DUPLICATE` row; the report's `possible_duplicates[]` is unchanged (immediate feedback preserved).
- **Traceability** (no schema change): each bulk review stores `submitted_payload = {source:"bulk_upload", batch:<id>, row:<n>, uploaded_by, name/mobile/email}` and a `detection_reason` naming the batch + row; `created_by` = the uploader.
- **Unchanged:** CREATED/UPDATED rows create no review; candidate status, lifecycle, rejection counter, Talent Pool, permissions, and the review model/serializers/APIs/Admin UI are untouched (reused as-is).
- **Verified** — 171 backend tests (bulk persists a PENDING review with traceability; dedupe across repeated uploads; no reviews for created/updated); existing single-create review tests still pass; `spectacular` 0 errors.

## [Pipeline] JD Tracker moved out of stage tabs → "Communications" button (UI only)
The **JD Tracker** tab was removed from the pipeline stage navigation — communication tracking isn't a recruitment stage. The stage tabs now end at **Awaiting Joining** (Shortlisted → JD Email Sent → Screening Scheduled → OK to Proceed → Offer Released → Awaiting Joining). A **Communications** button (next to the table search/Columns) opens the same `JdTracker` view in a dialog — reusing the existing backend/service, no functionality or data changed. Candidate drawer timeline (the single source of truth for the full lifecycle, incl. JD/communication events) is unchanged. Frontend-only; `tsc` + `vite build` clean.

## [Dashboard] Pipeline chart matches the board (starts at Shortlisted)
Removed **"New"** from the dashboard Pipeline-Stage chart so it uses the **same stage definitions as the Pipeline board** (applications begin at Shortlisted; outcomes excluded). Dashboard-visualization only — no lifecycle/business-logic change. (A short-lived "Awaiting Resume Review" KPI was added then removed per feedback — not needed.) Verified: 168 backend tests; `tsc` + `vite build` clean.

## [Pipeline] Stages vs. outcomes refactor + Offer Released / Awaiting Joining
Clean separation of **pipeline stages** (candidate position) from **recruiter actions** and **outcomes**. Lifecycle, permissions, rejection counter, duplicate detection and audit are unchanged.
**Stages (only):** New → Shortlisted → JD Email Sent → Screening Scheduled → OK to Proceed → **Offer Released** → **Awaiting Joining**.
**State machine (`STAGE_TRANSITIONS`) rebuilt:**
- **Schedule Screening is no longer a status/stage** — it's a recruiter action. Scheduling a round in the Screening module moves JD Email Sent → **Screening Scheduled** (migration drops `SCHEDULE_SCREENING`, migrating any in-flight app to Screening Scheduled).
- Screening Scheduled → OK to Proceed / Rejected / Fake (unchanged outcomes).
- OK to Proceed → **Offer Released** (was "Offered", renamed display; code kept `OFFERED`) / Rejected.
- **Offer Released → Offer Accepted (→ Awaiting Joining) | Offer Declined (close).** New `OFFER_DECLINED` outcome → Talent Pool, no rejection count.
- **Awaiting Joining → Joined (completes hire, consumes an Open seat) | Withdrawn (close).** The Join/position-consume moved here from Offered.
**Migration `0018`** — rename Offered→"Offer Released"; add `AWAITING_JOINING` + `OFFER_DECLINED`; migrate + drop `SCHEDULE_SCREENING`. No history touched.
**Dashboard & Pipeline board** now show only the 6 working stages (+ JD Tracker); outcome statuses stay in candidate timeline/reports. Dashboard pipeline chart order updated to the new stage flow.
**Timeline** unchanged in behaviour — every transition still logs to `candidate_interaction` (Offer Released / Offer Accepted / Offer Declined / Joined / Withdrawn all appear).
**Verified** — 168 backend tests (legal OK-to-Proceed→Offer Released; illegal JD→OK; offer accept→Awaiting Joining; offer declined→Talent Pool; join from Awaiting Joining; over-fill refused; screening schedule moves JD→Scheduled; dashboard stage order); `check` + `spectacular` 0 errors; `tsc` + `vite build` clean; `seed_demo` idempotent.

## [Dashboard] Position KPIs, full pipeline chart, duplicate-review task, filtered upload widget
All role-aware, reusing existing services/scopes — no lifecycle/permission changes.
- **Candidate-upload widget** (recruiter) now shows only the **recruitable pool** — same exclusion as the Candidates page (`CandidateStatus.DB_DEFAULT_HIDDEN`: Reject-Hold/Joined/Fake/Blacklisted). Added a **Candidates Available** KPI.
- **Total Positions** + **Filled Positions** KPIs on every role, role-scoped via one aggregate query on `RequirementPosition` (`_position_totals`): Admin → all; HM → `req__hiring_mgr=self`; Recruiter → `req__recruiter=self`.
- **Pipeline chart** is now the ordered full flow (`_pipeline_stages`, built from existing `application_stage` data, zero-filled): Shortlisted → JD Email Sent → Screening Scheduled → OK to Proceed → Offered → Joined → Withdrawn. Shown for **all roles**, each over their accessible mappings. (No new stages introduced — "Screening Completed"/"Offer Accepted" map to the closest existing stages.)
- **Pending Admin Tasks** gains **"Possible duplicates to review"** — count of `candidate_duplicate_review` in `PENDING` (reviewed/merged/dismissed excluded); the card deep-links to `/duplicate-reviews`.
- **Performance** — every addition is a single aggregate/`values().annotate()` query (no N+1).
- **Verified** — 168 backend tests (position KPIs role-scoped; pipeline order; duplicate task present; recruiter widget excludes hidden); `tsc` + `vite build` clean; `spectacular` 0 errors.

## [Candidates] Blacklisted vs Fake — mutually exclusive, reasoned, admin-reversible
**Separation** — a candidate can't be both **Blacklisted** and **Fake** at once. Marking one while the other is set returns a clear `400` ("… mutually exclusive — an admin must remove X before marking as Y"). Backend-enforced in `set-status`.
**Mandatory reason + audit** — `set-status` now requires a `reason`; it's recorded on the candidate timeline as `Marked <status>. Reason: …` with who/when (existing `CandidateInteraction` audit). History is never erased.
**Admin-reversible** — new **`POST /candidates/{id}/clear-status/`** (Admin-only) removes a Fake/Blacklisted mark and restores the candidate to **Talent Pool** so they can re-enter the workflow. Recruiters can't reverse it (403). Both statuses keep the candidate out of the Talent Pool / review pool until cleared (unchanged existing behaviour — lifecycle/rejection/duplicate logic untouched).
**Permissions fix** — `CandidateViewSet.get_permissions` now authoritatively scopes the custom actions (`set-status` = REC/ADM, `clear-status` = ADM); previously the `@action` permissions were shadowed by the override and fell through to any-authenticated.
**UI** — Candidate drawer: "Mark Fake/Blacklisted" prompts for a mandatory reason; once flagged, the mark options disappear and (for Admins) a **"Remove <status>"** button appears (non-admins see "Only an admin can remove this status"). Distinct badges kept: **Fake = red**, **Blacklisted = gray/black**.
**Verified** — 166 backend tests (mutual exclusivity, mandatory reason, clear-status admin-only + restores to Talent Pool, history preserved); `tsc` + `vite build` clean; `spectacular` 0 errors.

## [Candidates] Lifecycle automation — Reject-Hold, Joined retention, visibility
**Statuses** — added system-managed **Reject Hold** and **Joined** to `candidate_status_master` (Talent Pool = existing `SAVED`). New `candidate_master` fields (migration `0017`): `active_rejection_count`, `reject_hold_start`, `reject_hold_until`, `joined_date`, `last_status_changed_on`.
**Application-outcome automation** — integrated into the **existing** `transition_mappings` (no parallel path) via a single `apply_application_outcome` service:
- **Rejected** → `active_rejection_count += 1`; `<2` → Talent Pool, `==2` → **Reject Hold** (`reject_hold_until = today + 6 months`).
- **Dropped / No Response / Withdrawn / Not Suitable** → Talent Pool (no count).
- **Joined** → status Joined + `joined_date`.
- Hard dispositions (Fake/Blacklisted) and an already-Joined candidate are never overridden by a stray outcome.
**Daily maintenance** — `python manage.py run_candidate_lifecycle` (schedule via cron): Reject Hold → Talent Pool after 6 months (**counter reset**); Joined → Talent Pool after 2 years. `run_lifecycle_maintenance(as_of=…)` is the testable core.
**History preserved** — resetting the counter never deletes history; every status change appends a `STATUS_CHANGE` interaction (candidate timeline). `active_rejection_count` is a working field only.
**Manual status** — only **Fake / Blacklisted** are hand-settable now; Talent Pool / Reject Hold / Joined / New CV / Possible Duplicate are system-managed (set-status → 400 for those).
**Visibility (backend-enforced)** — candidate list default hides **Reject Hold / Joined / Fake / Blacklisted** for REC/ADM; `?status=<code>` filters, `?status=ALL` shows everything (search works across all). **Hiring Managers only ever see New CV + Talent Pool**, on every action (list *and* by-id) — no "All" override. Detail actions (retrieve/set-status) remain reachable by id for REC/ADM so a hidden candidate can still be acted on.
**Also fixed** — `seed_demo` now clears `candidate_duplicate_review` before candidates (FK).
**Verified** — 164 backend tests (first/second rejection, hold expiry + counter reset, joined 2-yr return, dropped/withdrawn, recruiter default + All, HM restriction, history intact after reset, scheduler); `check` + `spectacular` 0 errors; `tsc` + `vite build` clean; `seed_demo` idempotent.

## [Candidates] Duplicate Review workflow (separate from candidate status)
A dedicated process to detect, report, and resolve duplicates — **independent of the candidate lifecycle** (never sets `candidate_status = Possible Duplicate`; that value/flags stay unused).
**Detection (unchanged rules)** — same mobile/diff email → possible duplicate. Instead of a dead-end 409, the response now carries `{reason, existing_candidate, submitted}` so the UI can open a **read-only side-by-side** comparison.
**New table `candidate_duplicate_review`** (migration `0016`, managed model): new-candidate details, `existing_candidate` FK, detection reason, `review_status` (Pending/Resolved), `resolution` (Merged/Kept-Separate/Corrected), notes, and full audit (`created_by/on`, `resolved_by/on`) + `submitted_payload` JSONB for future merge.
**Recruiter** — on a detected duplicate, sees both records side-by-side with the reason and can **Submit for Admin review** or **Cancel**. Recruiters **cannot** merge or edit identity fields. `POST /duplicate-reviews/` (REC/ADM), dedupes an existing pending review.
**Admin** — new **Duplicate Review** page (admin-only route + nav) listing Pending/Resolved reviews. Actions per review: **Keep separate**, **Correct identity** (fixes the existing candidate's mobile/email → resolves as Corrected), **Merge** (records the decision; actual data merge deferred). `GET`/`resolve` are **Admin-only** (403 otherwise).
**Audit & safety** — every review records who/when created and resolved + the resolution; no candidate history is touched. Merge is intentionally a recorded decision only (per spec) — the review record is the entry point for full merge later, with no architecture change needed.
**Verified** — 146 backend tests (detection payload; create REC/ADM, HM 403; list/resolve Admin-only, others 403; CORRECTED fixes existing candidate; dedupe; already-resolved → 400; candidate_status never touched); `tsc` + `vite build` clean; `spectacular` 0 errors.

## [Fix] Seed derives requirement status from positions (no impossible states)
**Symptom** — the seed hardcoded each requirement's status (e.g. `Open`), so the UI could show impossible combinations like **Open with 1/2 filled**.
**Fix** — `seed_demo` no longer hardcodes `req_status`. After seeding positions + candidates it derives status with the **same production functions**: `open_requirement_on_first_link` (first candidate → Open) then `recompute_requirement` (positions rollup → Partial/Close Filled, and refreshes the filled cache). Manual states (Hold/Cancelled/Close Lost) remain explicit if set. Result (verified): REQ-2026-001 → **Partial Filled** (1/2), all 9 requirements consistent with their seats; no hardcoded status remains. **141 backend tests pass.**

## [Fix] Seeded Filled positions had no candidate (blank Assigned candidate)
**Symptom** — a position showed **Filled** but the *Assigned candidate* (and *Last updated*) column was blank.
**Root cause** — `seed_demo` created Filled seats via `bulk_create` (using the count of `OK_TO_PROCEED` candidates) **without setting `filled_by_mapping`**, and those candidates weren't actually Joined. The real fill path (`_consume_open_position`, on Join) always links the mapping — only the seed bypassed it. So a Filled seat existed with no candidate reference.
**Fix** — seed now creates all seats **Open**, then fills them the way production does: the OK-to-Proceed candidates are seeded as **Joined** (with `joined_date`) and each is **linked to a seat via `filled_by_mapping`** (+ `updated_on`). Result: every Filled position references its candidate. Verified: **0** Filled positions lack a candidate link; REQ-2026-001 Position 1 now shows *Rahul Sharma* + a Last-updated date.
**No code/UI change needed** — the serializer/UI already surface `filled_by_candidate`/`updated_on`; this was purely a seed data-integrity bug. Going forward, Filled is only reachable via the auto Join path (which links the mapping) or is blocked manually, so the case can't recur. **141 backend tests pass.**

## [Positions] Position management workflow + Requirement Details page
**Requirement Details page** — clicking a requirement (row or View) now opens `/requirements/:id` with **Overview** and **Positions** tabs (replaces the old read-only View dialog, which was removed). Recruiters get a dedicated **Eye** button → same page (read-only).
**Positions tab** — lists each position: **Position N · Status (colored badge) · Assigned candidate · Last updated · Actions**. Badges use a shared `positionStatusVariant` (Open=teal, Hold=amber, Filled=green, Cancelled=red).
**Position status workflow (backend-enforced, HM-only):**
- Manual transitions: `Open↔Hold`, `Open/Hold→Cancelled`, `Cancelled→Open` (reopen) — via `change_position_status` (new guard) behind the `set-position-status` endpoint.
- **`Filled` is never manual** (rejected `400`) and is **terminal** (no transitions out); a seat fills **automatically** when its candidate reaches **Joined** (unchanged `_consume_open_position` path).
- **Recruiter & Admin are read-only** on position status → `403`; only **HM** can change it. The ⋮ actions menu shows only to HM (status-aware); recruiters/admins see none.
**Independence preserved** — cancelling/reopening a *requirement* never touches position statuses, and vice-versa. Position changes still **drive** the calculated requirement statuses (Partial Filled / Close Filled) via the existing rollup; Close Lost still comes from a requirement cancel with unfilled seats. Positions are still auto-created at requirement creation (so they exist once it's Open), each starting `Open`.
**No schema change.** Serializer now returns `updated_on` (for "Last updated"). **Verified** — 141 backend tests (HM Open/Hold/Cancel/reopen; manual Filled → 400; Filled terminal → 400; Recruiter & Admin → 403; Join still auto-fills); `tsc` + `vite build` clean; `spectacular` 0 errors.

## [Requirements] HM lifecycle actions available across all active states
Hold/Cancel were only offered from `Open`. Now **all active states — `Assigned`, `Open`, `Partial Filled` — expose the same HM lifecycle actions** (View, Edit, Put on Hold, Cancel), because a recruiter assignment doesn't transfer ownership: the Hiring Manager keeps full control throughout the active lifecycle.
**Backend** (required for the buttons to actually work, not just appear): `MANUAL_REQ_TRANSITIONS` gained `ASSIGNED → {Hold, Cancel}` and `PARTIAL_FILLED → {Hold, Cancel}` — **additive only**; no existing transition, the Cancel→Close Lost rule, or any business logic changed. `Cancel` from Assigned/Partial still resolves to **Close Lost** (unfilled seats).
**Frontend** — `manualStatusActions` returns the Open action set for `ASSIGNED`/`PARTIAL_FILLED` too. Unchanged: New → View/Edit; Hold → View/Edit/Resume/Cancel; Cancelled/Close Lost → View/Reopen; Close Filled → View.
**Verified** — 138 backend tests (HM Hold from Assigned; HM Cancel from Partial → Close Lost; existing illegal transitions still 400); `tsc` + `vite build` clean.

## [Requirements] RBAC permission matrix — split lifecycle (HM) vs. assignment (Admin)
Sharpened who can do what on a requirement (enforced **both** in the UI and on the API):

| Action | Admin | Hiring Manager | Recruiter |
|---|---|---|---|
| View | ✅ | ✅ | ✅ (read-only) |
| Assign / Reassign recruiter | ✅ | ❌ | ❌ |
| Edit | ❌ | ✅ | ❌ |
| Hold / Resume / Cancel / Reopen | ❌ | ✅ | ❌ |

**Backend** — `update`/`partial_update` and `set-status` are now **Hiring-Manager-only** (`IsHiringManager`); `assign` stays **Admin-only** (`IsAdministrator`). Any out-of-role call → **403**. (Create/delete/position-seat actions are unchanged — HM+Admin.)
**Frontend** — the row ⋮ menu is now role-shaped: **Admin** sees only *View* + *Assign/Reassign* (no lifecycle); **HM** sees the status-aware *View/Edit/Hold/Resume/Cancel/Reopen* set (no Assign); **Recruiter** has **no menu** — just a dedicated **Eye (View)** button that opens the existing `RequirementViewDialog` read-only.
**Verified** — 136 backend tests (Admin edit/set-status → 403; HM assign → 403; HM lifecycle still works; assign Admin-only) ; `tsc` + `vite build` clean; `spectacular` 0 errors.

## [Requirements] Row actions (⋮) menu + Reopen + Assign is Admin-only
**Contextual ⋮ menu (HM/Admin, per row)** — replaces the standalone Assign button; recruiters see no menu. Items are status- and role-aware:
- **View** (all) — read-only details dialog (`RequirementViewDialog`).
- **Edit** (non-terminal) — opens the requirement form in edit mode (new `useUpdateRequirement` PATCH; positions are managed separately so `positions_open` is read-only in edit).
- **Status transitions** — Open → Put on Hold / Cancel; Hold → Resume / Cancel; **Cancelled or Close Lost → Reopen** (→ Open). Cancel confirms first; the list refreshes after every change.
- **Assign/Reassign recruiter** — **Admin only** item.
**New backend transition** — `Cancelled → Open` and `Close Lost → Open` (Reopen) added to `MANUAL_REQ_TRANSITIONS`; reopening restores the requirement to Open **without touching positions, candidates, or history** (a cancel never modified them).
**Assign is now Admin-only** — the `assign` endpoint permission changed from HM/Admin to **Admin** (`IsAdministrator`); HM & Recruiter → `403`. The Assign UI is hidden (not disabled) for HM/Recruiter. HM retains full lifecycle control (Hold/Resume/Cancel/Reopen).
**Enforced both ends** — frontend hides what a role can't do; backend permissions are authoritative.
**Verified** — 134 backend tests (reopen from Cancelled & Close Lost; assign HM→403 / Rec→403 / Admin→200; plus existing workflow); `check` + `spectacular` 0 errors; `tsc` + `vite build` clean.

## [Requirements] Event-driven status workflow + Overdue indicator
**Status is no longer free-form** — `req_status` was removed from the write serializer, so it can never be set by create/update. It changes only via:
- **Event-driven:** create → `New`; assign recruiter → `Assigned`; **first candidate linked → `Open`** (new `open_requirement_on_first_link`, called from `review_candidate` when the first mapping is created).
- **System-derived from positions** (rollup): `Partial Filled` (≥1 seat filled, not all), `Close Filled` (all filled). **Position cancellation never touches requirement status** — the two lifecycles are independent, so cancelling every seat leaves the requirement where it is (requirement `Cancelled` is manual-only).
- **Manual (HM/Admin only)** via new `POST /api/requirements/{id}/set-status/`: `Open↔Hold`, and **Cancel** from Open/Hold. A Cancel with seats still unfilled resolves to the system status **`Close Lost`**. Illegal targets (New/Assigned/Open-on-link/Partial/Close Filled) → `400`; **recruiters → `403`** (they can never change requirement status). The state machine lives in `change_requirement_status`.
- **No "Expired"** in the workflow — the status master is unchanged (the code still exists) but the workflow never assigns it.
**Overdue indicator (replaces Expired) — UI, informational only:** if today is past a requirement's **Target Closing Date** (`target_fill_date`) and it's still open, the Requirements list shows an amber ⚠ **"Overdue"** pill with a hover tooltip ("…review, extend the target date, or close the requirement"). It **does not** change status or any calculated state; extend the date and it disappears; no target date → no indicator; closed requirements never show it.
**UI:** Requirements list gained the Overdue pill in the Status cell and a per-row status-actions menu (Hold/Resume/Cancel) for HM/Admin (Cancel confirms first).
**No schema change.** **Verified** — 130 backend tests (first-link→Open, Hold/Resume, Cancel→Close Lost, illegal transitions→400, recruiter→403, status not settable via create/update); `check` + `spectacular` 0 errors; `tsc` + `vite build` clean.

## [RBAC] Role-based data visibility for requirements (+ pipeline/positions)
**What** — recruiters now see only requirements **assigned to them**; hiring managers see only requirements they **own**; **admins are unrestricted**. Backend-enforced, not UI filtering.
**How** — scoped `RequirementViewSet.get_queryset` by role (REC→`recruiter_id`=self, HM→`hiring_mgr_id`=self, ADM→all, unknown→none). Because retrieve, the `positions` action, `assign`, `set-position-status` and updates all resolve through `get_object()`, a recruiter/HM hitting **another** owner's requirement by id gets **404** — direct API calls can't reach another recruiter's data. Search, filters, ordering and pagination run on top of the scoped base queryset (counts reflect only visible rows).
**Already scoped (no change needed):** Pipeline endpoints (`_get_requirement_for_recruiter` already enforces assigned-recruiter + admin-bypass) and the role dashboards (`dashboard_service` filters by `recruiter`/`hiring_mgr`). Positions have no global list — only the per-requirement action, which is now covered.
**Candidates unchanged** — the candidate database stays **shared** (search all, view all, attach existing to your own requirements); no visibility restriction, as specified.
**No schema / no workflow / no UI change** — the frontend simply renders the now-scoped API responses.
**Verified** — 122 backend tests (3 new: recruiter sees only assigned + 404 on another's detail/positions; HM sees only owned; admin sees all) exercised over HTTP; `check` + `spectacular` 0 errors.

## [Candidates] Color-coded profile-status badges (UI only)
**What** — candidate profile-status badges now use a distinct, consistent colour per status so recruiters recognise status at a glance: **New CV → blue**, **Talent Pool (SAVED) → purple**, **Possible Duplicate → orange**, **Fake → red**, **Blacklisted → gray/black**.
**Centralized** — one map, `candidateStatusVariant(code)` in `lib/status.ts` (keyed by **code**, not display name, so colour is stable across renames), reused by every candidate-status badge (candidate list `columns.tsx` + Candidate Details drawer). No colours hardcoded in components.
**Badge** — added reusable `blue` / `purple` / `orange` / `neutral` variants to the shared `Badge` (light bg + dark text, each with a `dark:` fallback). Pill shape/padding/font unchanged — only colour. Existing variants untouched, so all other badges (requirements, pipeline stages) are unaffected.
**No data change** — status names/codes/DB values untouched; purely presentational (pairs with the "Talent Pool" label over code SAVED).
**Verified** — `tsc` + `vite build` clean; palette utilities confirmed present in the built CSS (no Tailwind purge issues).

## [Candidates] Profile-status workflow — system vs. manual statuses
**Rules** — a candidate's global profile status now has clear ownership. **System-assigned:** `NEW_CV` on creation (manual + bulk, already via `upsert_candidate`) and `POSSIBLE_DUPLICATE` on duplicate detection (unchanged mobile-UNIQUE + 409 resolution flow). **Recruiter-settable (manual):** only `SAVED` (shown as **"Talent Pool"**), `FAKE`, `BLACKLISTED`.
**Backend** — new `POST /api/candidates/{id}/set-status/` (REC/ADM) with a `CandidateStatusChangeSerializer` whose `ChoiceField` is restricted to `CandidateStatus.MANUAL_CHANGEABLE = (SAVED, FAKE, BLACKLISTED)` → `NEW_CV`/`POSSIBLE_DUPLICATE`/unknown codes are rejected with `400`. The change is written with audit fields and logged as a `STATUS_CHANGE` interaction (appears on the candidate timeline). The write serializer still does **not** expose `candidate_status`, so PUT/PATCH can't bypass the whitelist.
**Frontend** — Candidate Details drawer gains a **"Change status"** dropdown (REC/ADM only) offering exactly Talent Pool / Fake / Blacklisted; the current status is disabled. Status badges (candidate table + drawer) show **"Talent Pool"** for the `SAVED` code via `candidateStatusLabel()` — a UI label only.
**No schema/code change** — status codes and `candidate_status_master` are untouched; "Talent Pool" is a presentation label over code `SAVED`.
**Verified** — 119 backend tests (allowed codes succeed + land on timeline; `NEW_CV`/`POSSIBLE_DUPLICATE`/bogus → 400, status unchanged); `check` + `spectacular` 0 errors; `tsc` + `vite build` clean.

## [Candidates] Requirement-aware activity timeline (UX only)
**Why** — the candidate drawer's global activity timeline mixed application events (stage change, JD email, screening, …) without saying *which* requirement they belonged to. A candidate applied to several reqs had an ambiguous feed.
**Timeline (global)** — stays a single chronological feed of everything that happened to the candidate. Each **application** event is now tagged with its **Requirement name + tracker no** and shows the **recruiter** who performed it (`by <name>`). **Candidate-level** events (Candidate added / import) stay in the feed with no requirement tag.
**Requirement history (per application)** — each requirement card is now expandable ("View timeline"), revealing that one application's timeline (the global feed filtered to that requirement). Goal: *Timeline = across all applications, tagged*; *Requirement history = one application in detail*.
**How** — backend `candidates` `detail` endpoint now attaches `req_id`/`req_tracker_no`/`req_role` to each timeline event (from the existing `CandidateInteraction.req` / `CommunicationLog.req` FKs — no schema change, no new query cost beyond `select_related`). Frontend extracted a reusable `TimelineList` + a `RequirementCard` that filters events by `req_id`.
**Preserved** — audit logs, business logic, and data untouched; this is presentation only.
**Verified** — drove `/api/candidates/<id>/detail/` directly: application events carry "Senior Java Developer / REQ-2026-001 · by Rajeev Mehta", candidate-add event stays context-free. 115 backend tests pass; `tsc` + `vite build` clean.

## [Pipeline] Consolidate status model — one `application_stage`, remove `cv_status`
**Why** — `cv_status` (the resume-review verdict, added in `0013`) duplicated information the pipeline stage already carries. Two per-application "status" fields meant two things to keep in sync. Collapsed to a single source of truth.
**Model** — `jd_cv_mapping.application_stage` is now the **only** per-application progress field. `candidate_master.candidate_status` (global disposition) is unchanged.
**Data (`0015`)** — dropped `jd_cv_mapping.cv_status`. Before dropping, promoted review "Not Suitable" outcomes to the dedicated **`NOT_SUITABLE`** stage (old model set those to `REJECTED` + `cv_status=NOT_SUITABLE`). Shortlisted verdicts needed no action — their stage was already `SHORTLISTED` or had legitimately progressed, so the backfill deliberately does **not** rewrite them (no regression of in-pipeline candidates).
**Behaviour** — Review now sets only the stage: **Shortlist → `SHORTLISTED`**, **Not Suitable → `NOT_SUITABLE`** (was `REJECTED`). Rejection reason still captured on Not Suitable. No other business logic changed (state machine, exits, screening rules all intact).
**Backend** — removed the `cv_status` field + serializer fields (`cv_status`/`cv_status_label`) + review-response key + candidate-detail keys. Removed the obsolete **`CvStatus`** constant registry (legacy, named after the dropped `cv_status_master`); `seed_demo` now uses `ApplicationStatus`/`CandidateStatus`.
**Frontend** — dropped `cv_status`/`cv_status_label` from the `Mapping` type; **removed the "CV status" column** from the pipeline table (the active tab already shows the stage) and replaced it with a **"Last updated"** column.
**Verified** — 115 backend tests pass; `check` + `spectacular` (0 errors); `tsc` + `vite build` clean; `seed_demo` re-seeds cleanly. No stray `cv_status`/`CvStatus` refs remain (only accurate redesign-history comments).

## [Pipeline] Rename `jd_cv_mapping.application_status` → `application_stage`
**Why** — the per-application field holds the pipeline **stage** (Shortlisted → JD Sent → Screening → … → Joined), not a "status". Renaming disambiguates the three status concepts: `candidate_master.candidate_status` (global disposition) vs `jd_cv_mapping.application_stage` (pipeline stage) vs `jd_cv_mapping.cv_status` (resume-review verdict).
**Data (`0014`)** — pure column **rename** `jd_cv_mapping.application_status_id → application_stage_id` (idempotent, no data moved/lost). The FK still points at `application_status_master` — the **stage catalog** (table, `ApplicationStatus` constants, and the `/api/application-status/` admin endpoint) keeps its name; only the per-application field was renamed.
**Backend** — model field `application_stage`; all services/serializers/views/filters/`select_related`/`update_fields`/seed updated. **API response fields renamed**: `application_status_name` → **`application_stage_name`**, `application_status_code` → **`application_stage_code`** (the FK id field is now `application_stage`).
**Frontend** — `Mapping` type fields renamed to `application_stage_name`/`_code`.
**UI terminology** — Candidates table header → **"Candidate Status"**; Pipeline stage tabs now labelled **"Application Stage"**.
**Note** — `cv_status` (the review verdict) is unchanged; it is a separate concept and was intentionally **not** removed.
**Verified** — 115 backend tests pass; `manage.py check` + `spectacular` (0 errors); `tsc` + `vite build` clean; `seed_demo` re-seeds cleanly (25 pipeline rows). Repo-wide sweep confirms no stray `application_status` field refs remain (only the master table/PK/constant/endpoint, kept by design).

## [Pipeline] Review = resume-review only; CV status vs Application status separated
**Why** — the Review action mixed two concepts: application decisions (Shortlist / Not Suitable) and candidate-disposition actions (Save for later / Mark fake). Review should be the recruiter's **initial resume review** only.
**Data (`0013`)** — new **`jd_cv_mapping.cv_status`** = the resume-review verdict (`SHORTLISTED` / `NOT_SUITABLE`), a per-requirement judgement kept **separate** from `application_status` (the pipeline stage). Backfilled for existing applications.
**Behaviour** — Review now offers only **Shortlist** / **Not Suitable** (Save/Fake removed — candidate-disposition is a separate concern):
- **Shortlist** → `cv_status = Shortlisted` **and** stage → `Shortlisted` (keeps the existing Send-JD → Screening flow).
- **Not Suitable** → `cv_status = Not Suitable` **and** stage → `Rejected` (application closed); rejection reason captured.
- The candidate stays **in the pool** (global `candidate_status = Saved`) — a per-requirement verdict never changes the candidate's global disposition.
- Every review is written to the application's **activity timeline**.
**Backend** — `review_candidate` rewritten (2 decisions; sets both statuses); `REVIEW_DECISIONS = [SHORTLISTED, NOT_SUITABLE]` (Fake/Save removed) so the API rejects the old options. `JdCvMappingSerializer` + candidate-detail requirement-history expose `cv_status` + `cv_status_label`.
**Frontend** — Review dropdown trimmed to Shortlist / Not suitable; pipeline rows show a **CV status** badge; `ReviewInput.decision` narrowed.
**Also fixed** — (1) `seed_demo` now clears `screening` rows before deleting applications (a latent FK gap from the screening feature); (2) `ReviewView` response referenced the removed `candidate.cv_status` (a stale field from the 0008 cutover that only the HTTP path hit) → now `candidate_status`; added **API-level** review tests so the view path is covered, not just the service.
**Verified** — 115 backend tests pass (shortlist sets cv_status+stage; not-suitable → Rejected; review offers only the two decisions; review HTTP endpoint returns 200 with cv_status; removed decisions → 400); `tsc` + `vite build` clean; OpenAPI 0 errors; `seed_demo` idempotent. No unrelated modules changed.

## [Pipeline] Sequential Screening workflow (screening rounds)
**Why** — screening supported only a single Telephonic/Video selection; real recruitment runs sequential rounds (Telephonic → outcome → Video → outcome → ready for interview) each with its own outcome, interviewer and notes.
**Data** — new **`screening`** table (migration `0012`): one row per round, linked to the application (`jd_cv_mapping`). Type = FK to `screening_mode_master` (**extensible** — add a mode, get a new screening type, no code change). Status (`Scheduled`/`Completed`) and outcome (`Passed`/`Failed`/`No Show`/`Cancelled`/`Reschedule Required`) are fixed workflow enums; `interviewer` is free-text (supports external panels). The legacy inline `jd_cv_mapping.screening_mode/screening_datetime` are left in place (unused) so nothing breaks.
**Rules** (enforced in `pipeline/screening.py`, the single write-path): no new round while one is still Scheduled · Video only after a Telephonic is completed **Passed** · a repeat Telephonic only when the previous outcome was **Reschedule Required** · a closed application (Rejected/Not Suitable/Dropped/Withdrawn/Joined) accepts no screenings · an application may advance to **OK to Proceed** only when its latest screening is **Passed** (enforced in `transition_mappings`; legacy applications with no screenings are unaffected). Every schedule/complete is written to the application's activity timeline (`candidate_interaction`).
**API** — `GET/POST /api/pipeline/screenings/` (list by `?mapping=`, schedule) + `POST /api/pipeline/screenings/{id}/complete/` ({outcome, notes}); recruiter-scoped like the rest of the pipeline. `ScreeningSerializer` + schedule/complete input serializers.
**Frontend** — the single "Set date & time" schedule dialog is replaced by a **Screening History** dialog (`ScreeningDialog`): chronological rounds with status/outcome badges, per-round "Record outcome", and an "Add screening" form (disabled while a round is open). Wired into the pipeline stage board's screening stages; the old `ScheduleDialog` was removed.
**Verified** — 111 backend tests pass (incl. video-needs-passed-telephonic, no-concurrent-open, repeat-only-on-reschedule, rejected-blocks, OK-to-Proceed-needs-passed, timeline entry); `tsc` + `vite build` clean; OpenAPI 0 errors; `seed_demo` idempotent. No unrelated modules touched.

## [Dashboard] Admin dashboard — drill-downs, idle heat, real admin tasks
Refinement (not a redesign) making the Admin dashboard actionable:
- **KPI cards are drill-downs** — each navigates to the relevant module with a filter (Active Requirements/Open Positions → `/requirements?status=active`, Joined This Month → `?status=CLOSE_FILLED`, Active Recruiters/Clients → `/admin?resource=…`, In Pipeline → `/pipeline`). `StatCard` gained an optional `to` prop (renders as a link with hover/focus states).
- **Deep-link filters added** to existing screens (no new pages): `RequirementsPage` honours `?status=` (incl. an `active` group), `?missing=recruiter|hm`, and `?q=`, with a dismissible filter chip + count; `MasterDataPage` honours `?resource=`. This is how every dashboard element "opens" its target.
- **Needs attention** — colour-coded idle heat (green <7d · yellow 7–14 · orange 15–30 · red >30) and each row opens the requirement (filtered list).
- **Pending admin tasks** — replaced the recruiter-owned "possible-duplicate candidates" with genuine admin oversight: **Requirements without a recruiter / without a hiring manager / On hold 30+ days / Inactive users**; each row (when count > 0) deep-links to the list that resolves it.
- **Top clients** rows are clickable (→ that client's active requirements); already showed active-reqs + open-positions.
- **Recent requirements** show the real requirement status (Open/Hold/Closed…) and each row is clickable.
- **Recent activity** already had per-type icons; rows now link to the related requirement where applicable.
- **Removed** the redundant "… workspace" label from the Topbar (the sidebar already conveys brand + role).
- Meaningful empty states throughout ("all clear" / "nothing stalled" / filter-specific empties).
**Note (recommended follow-up, not built):** clicking a requirement currently filters the Requirements list to it — there is no dedicated Requirement Details view yet. A read-only **Requirement detail drawer** (mirroring the Candidate drawer) is the enterprise-proper next step; flagged rather than invented, since it's a new screen.
**Verified** — 105 backend tests pass; `tsc` + `vite build` clean.

## [Dashboard] Admin — remove Quick Actions, add Pending Admin Tasks
**Why** — the Quick Actions (New Requirement / Add Candidate / Master Data) were operational shortcuts that belong to Hiring-Manager/Recruiter workflows (and Master Data is already in the left nav), which conflicts with the Admin dashboard's role as a **monitoring/administration** screen.
**Removed** — the Quick Actions header buttons (and the `QuickActions` component). They lived in the page-header action slot, so nothing left a body gap; the header is simply full-width now.
**Added (oversight value, not operations)** — a **Pending admin tasks** card surfacing the Admin's own to-dos: *Requirements without a recruiter* (active + unassigned) and *Possible-duplicate candidates to resolve* (data hygiene). Backend `_admin_tasks` in `dashboard_service`; each item is a `{key,label,count}` (a 0 count reads as "all clear").
**Rebalanced layout** — Needs attention (8) + Pending admin tasks (4) · Top clients (4) + Recent requirements (8) · Recent activity full-width. Every row sums to 12; responsive and gap-free.
**Verified** — 105 backend tests pass (admin payload now includes `admin_tasks`, still no operational keys); `tsc` + `vite build` clean.

## [Dashboard/Audit] Real activity log + accurate Joined date
**Why** — the Admin activity feed was *derived* from timestamps (approximate, couldn't capture events like "assigned"), and Joined-This-Month was proxied off `updated_on`. These are now first-class.
**Schema (`0011`)** — new **`activity_log`** table (audit feed: `activity_type`, `summary`, optional `req`/`candidate`/`actor`, `created_on`) + **`jd_cv_mapping.joined_date`** (the real join date). Backfilled: `joined_date` for existing JOINED rows; the feed seeded from existing requirement/candidate history.
**Backend** — `core/activity.log_activity()` (best-effort append; an audit write never breaks the business action) records: requirement **created** / **assigned** / **closed (filled)**, candidate **added**, candidate **joined**. Joining now stamps `joined_date`. `ActivityLog` model added. Dashboard `recent_activity` reads the log (not derived); `joined_this_month` counts `joined_date` in the current month. `seed_demo` clears + repopulates the feed.
**Frontend** — activity feed gains the `requirement_assigned` type/icon; otherwise unchanged (already reads `recent_activity`).
**Verified** — 105 backend tests pass (incl. a Join now writes `joined_date` + a `candidate_joined` audit row); OpenAPI 0 errors; `tsc` + `vite build` clean; `seed_demo` idempotent (feed rebuilt from history).

## [Dashboard] Admin dashboard redesigned for business oversight
**Why** — the Admin dashboard showed vanity totals (all-time Requirements/Candidates/Skills/Users) and **operational** widgets (pipeline-by-stage, per-candidate list) that belong to recruiters. It didn't answer the questions an Admin actually asks (active demand, outcomes, who/what needs attention).
**Role separation** — Admin now gets a **high-level business overview**; Hiring Manager/Recruiter dashboards are unchanged (still their operational views). Rendering split into `AdminDashboard` vs `OperationalDashboard` in [DashboardPage.tsx](frontend/src/features/dashboard/DashboardPage.tsx).
**KPIs (business, not totals):** Active Requirements · Open Positions · In Pipeline (distinct candidates in active stages) · **Joined This Month** · Active Recruiters · Active Clients. (Dropped Skills/Users/all-time counts.)
**Sections:**
- **Requirements by status** (donut) + **Recruiter workload** (now counts *active* reqs vs. *in-pipeline* candidates) — kept, both Admin-appropriate.
- **Top clients** by current hiring activity (active reqs + open seats) — new (client monitoring).
- **Needs attention** — requirements with open seats and **no activity for 14+ days** (idle = latest of requirement/application update); shows client, recruiter, open seats, idle days — new.
- **Recent requirements** enriched with Client · Recruiter · filled/required.
- **Recent activity** feed (requirement opened / candidate joined / requirement closed), newest first — new.
- **Quick actions** (New Requirement · Add Candidate · Master Data) in the header.
- **Removed from Admin:** pipeline-by-stage chart + per-candidate list (operational — recruiter screens).
**Backend** — `dashboard_service.build_dashboard` ADMIN branch rewritten with helpers `_top_clients`, `_stalled_requirements`, `_recent_activity`, enriched `_recent_requirements`; active/terminal/in-pipeline status sets centralised. Open Positions counts `requirement_position` OPEN seats (source of truth). No schema change.
**Recommended future (not implemented — would need schema):** a dedicated `activity_log`/audit table (the feed is derived from timestamps + status today) and a real `joined_date` on the application (Joined-This-Month currently uses the JOINED row's `updated_on` as a proxy).
**Verified** — 105 backend tests pass (incl. admin payload is business-level + operational keys absent; recruiter still operational); `tsc` + `vite build` clean.

## [Master Data] Fixes — single Code error message + Client Code lifecycle
**Duplicate validation message** — the Code field showed its error twice: the auto-code create branch rendered its own error/helper *and* the shared trailing `{err && …}` fired for the same field. `ResourceForm` now suppresses the shared error+hint for the auto-code field (each branch owns its message) → exactly one message.
**Client Code** now follows the same permanent-identifier lifecycle as the other masters: auto-generated from the client name (`Tata Consultancy Services → TATA_CONSULTANCY_SERVICES`), **editable once before the first save** (e.g. shortened to `TCS`, stops auto-updating after a manual edit), then **read-only/frozen** after creation (renaming the client never changes the code), unique + format-validated. Added `auto_code` to the `client_master` rule + the `clients` config's `autoCode`; migration `0010` widened `client_master.client_code` to `VARCHAR(50)` (model `max_length` too). Existing client codes (`TCS`, `INFY`, …) unchanged.
**Verified** — 102 backend tests pass (incl. client code auto-generated + frozen on rename, and one-time edit honored); `tsc` + `vite build` clean.

## [Master Data] Code — auto-generated, one-time editable on create, then frozen
**Why** — Code should be a stable internal key for APIs / business logic / reporting, while Name is the free-to-rename display value. Admins get a single chance during creation to shorten it (`CTC_IS_TOO_HIGH → CTC_HIGH`, `Interview Not Attended → NO_SHOW`).
**Behaviour** — for the status/type/mode masters (req-status, candidate/application/position-status, work-modes, screening-modes, rejection-reasons, req-types):
- **Create** — Code auto-fills from the Name (UPPER_SNAKE; `Screening Scheduled → SCREENING_SCHEDULED`, `JD Email Sent → JD_EMAIL_SENT`) and keeps following the Name **until the admin edits it once**; after that it stops auto-updating. The field is editable and validated: **required, unique, uppercase, starts with a letter, `A–Z`/`0–9`/`_` only**.
- **Edit** — Code is **read-only** (lock icon + "permanent system identifier" helper); the API drops any code field on update, so renaming Name/Description/Status never changes it.
- **Backend** — on create, a supplied code is honored (normalised via `generate_code`) or derived from the name, format-checked (`^[A-Z][A-Z0-9_]*$`) and dedup-checked (duplicates rejected). On update the code is never touched.
**Implementation** — `core.validation.generate_code()` + per-master `auto_code: {field, source}` rule; `MasterDataViewSet._resolve_code()` (create) + code-strip (update). Frontend `generateCode()` + `ResourceConfig.autoCode`; `useMasterForm` regenerates the code from the name until `editCode()` is called, validates it on create, freezes+omits it on edit; `ResourceForm` renders an editable code input on create and a locked read-only field on edit. Migration `0009` widened all code columns to `VARCHAR(50)`.
**Scope note** — `client_code` (`TCS`) and `template_code` (`JD_EMAIL`) stay **user-entered** — a one-line `auto_code` rule would include them later.
**Existing data** — untouched; only new records get generated codes.
**Verified** — 100 backend tests pass (code generated when omitted; supplied code honored on create; invalid code rejected; code frozen across a rename); `tsc` + `vite build` clean; OpenAPI 0 errors.

## [Recruitment Redesign] Positions + Candidate/Application status split — Phases 1–3 (partial, in progress)
**Design:** [docs/POSITION_REDESIGN.md](docs/POSITION_REDESIGN.md) (approved to build incrementally). Introduces a **Position** (seat) entity with its own lifecycle and splits the overloaded `cv_status_master` into **candidate disposition** vs **application (pipeline) status**.
**Phase 1 — `0006` (additive schema, applied):** new `candidate_status_master` (New CV/Saved/Fake/Possible Duplicate/Blacklisted), `application_status_master` (New/Shortlisted/JD Email Sent/No Response/Dropped/Schedule Screening/Screening Scheduled/Not Suitable/Rejected/OK to Proceed/Offered/Joined/Withdrawn), `position_status_master` (Open/In Progress/Closed/Cancelled/Hold); `requirement_position` table (`filled_by_mapping_id` FK → winning application); nullable `candidate_master.candidate_status_id` + `jd_cv_mapping.application_status_id`. Django models added. Non-breaking (app still reads legacy `cv_status`).
**Phase 2 — `0007` (backfill, applied):** mapped legacy `cv_status` → the new masters (candidate subset + pipeline subset; a mapping's `Fake` → `Not Suitable`); generated `requirement_position` rows per requirement (`positions_open` seats, first `positions_filled` Closed). Verified: 0 nulls; 16 seats across 9 requirements aligned to the counters.
**Phase 3 — backend cutover (done; mentor-confirmed rules):** `core/constants.py` +`CandidateStatus`/`ApplicationStatus`/`PositionStatus`. New `requirements/positions.py` — single write-path for seats: `create_positions_for_requirement` (one Open seat per opening, on requirement create), `recompute_requirement` (derived **rollup**: 0 filled→Open/Assigned, `0<filled<total`→Partial Filled, `filled==total`→Close Filled; manual Hold/Cancelled/Close Lost preserved) + over-fill-safe `set_position_status`. Position terminal state named **Filled** (renamed from Closed per the mentor). Pipeline (`pipeline/services.py`) **dual-writes** the new `application_status`/`candidate_status` (authoritative) while mirroring legacy `cv_status`, so nothing that still reads `cv_status` breaks; status reads use `application_status` with a legacy fallback. Workflow extended through **Offer → Joined**: `SCREENING_SCHEDULED→OK_TO_PROCEED→OFFERED→JOINED` (+ Rejected/Withdrawn/No-Response). **Reaching `Joined` consumes one Open position (→ Filled, linked to the winning application) and rolls up the requirement; refused (over-fill-safe) when no seat is free.** Per the mentor: **no auto-withdraw** of other applications; position status is **independent** of application status (only the explicit Join consumes a seat); `In Progress` stays manual. New API: `GET /api/requirements/{id}/positions/` (any auth), `POST /api/requirements/{id}/set-position-status/` (HM/Admin). The 3 new masters exposed as Admin-managed resources (`/api/candidate-status/`, `/api/application-status/`, `/api/position-status/`). `JdCvMappingSerializer` +`application_status_name`/`_code`. `seed_demo` materialises seats.
**Phase 3 — frontend (done):** pipeline **StageBoard** gains **OK to Proceed → Offered → Joined** tabs with actions (Make offer; Mark joined / Withdrawn / No response); a Join that has no free seat surfaces the server's `invalid` message. New **`PositionsPanel`** ([features/requirements/PositionsPanel.tsx](frontend/src/features/requirements/PositionsPanel.tsx)) on the Pipeline page — per-seat status chips + a `filled/active` count, with HM/Admin manual seat management (Reopen / In progress / Hold / Cancel; `Filled` is reachable only via a candidate Joining). New `usePositions`/`useSetPositionStatus` hooks; pipeline invalidation now also refreshes `positions` + `requirements` so a Join updates seats and the rolled-up requirement status live. The 3 new status masters are Admin-managed in the Master Data screen (Candidate / Application / Position Status).
**Phase 4 — `0008` legacy cleanup (done):** dropped `candidate_master.cv_status_id`, `jd_cv_mapping.cv_status_id` and the mixed `cv_status_master`; removed the dual-write mirror. All readers switched to the new columns beforehand: dashboards (`application_status`/`candidate_status`), pipeline + candidate serializers (`application_status_name/_code`, `candidate_status_name/_code`), candidate views + review pool, `seed_demo` (Fake candidates no longer create an application). `CvStatusMaster` model/serializer/viewset + `/api/cv-status/` and its admin screen removed. **Candidate disposition and application/pipeline status are now the single source of truth.**
**Verified:** 95 backend tests pass (position materialisation, rollup, manual-Hold-survives, **Join consumes a seat**, **over-fill refused + other apps untouched**, Fake flips candidate, positions API list + HM/Admin-only set-status); `manage.py check` clean; OpenAPI 0 errors; frontend `tsc` + `vite build` clean; `seed_demo` idempotent (25 pipeline rows, 16 seats). **Redesign complete.**

## [Master Data] Domain promoted to controlled master data (Skill classification)
**Why** — "Domain" was a free-text column on `skill_master`, so the same concept was typed many ways and reporting/grouping was unreliable. Enterprise ATS best practice: Skills are dynamic, resume-facing master data; Domains are controlled classification data. Candidates/Requirements keep referencing **Skills only** — never Domains.
**Schema** — migration `0005_domain_master.sql` (applied): new `domain_master` (unique, audited, soft-deletable); `skill_master` gains `domain_id` FK → `domain_master`; existing free-text values backfilled into `domain_master` and linked; the old `skill_domain` column **dropped** (single source of truth — a domain rename now reflects on every linked skill automatically via the FK). 11 domains created, all 25 skills linked.
**Backend** — `DomainMaster` model + `DomainMasterSerializer`; `SkillMasterSerializer` now exposes `domain` (FK, **required**) + read-only `domain_name`; `DomainMasterViewSet` under `IsAdminOrReadOnly` (any auth reads for the dropdown; **Admin-only** create/edit/deactivate); registered at `/api/domains/`. Skill search moved to `domain__domain_name`. Shared master rules extended: `domain_master` normalises/validates `domain_name` as a `label` (allows "Data & Analytics", "UI/UX Design"); `skill_master` domain rule dropped (now a FK). A domain referenced by skills can only be **deactivated**, never permanently deleted (the base `/references` check sees `skill_master` via the reverse FK → 409). `seed_demo` seeds domains then links skills.
**Frontend** — free-text Domain replaced by a searchable **`DomainSelect`** combobox (active domains). Admins get a role-gated **"+ Add Domain"** action → the shared `MasterCreateDialog` (same validation/normalisation as every master); Hiring Managers get select-only (they may pick a domain when creating a Skill inline, but never create/edit/delete one). New `"domain"` field type wired through `useMasterForm.buildPayload` + `ResourceForm` + `MasterCreateDialog`. Domain management is a **lightweight section inside the Skill master** (not a separate page): extracted `ResourceManager` (the full table+form+two-tier-delete engine, reused for any master) and rendered it a second time for Domains under Skills; `MasterDataPage` slimmed to nav + `ResourceManager`, with `domains` hidden from the sidebar.
**Verified** — 88 backend tests pass (incl. domain required → 400, HM cannot create/edit domain → 403, admin create normalises "  data &  analytics " → "Data & Analytics", domain-in-use permanent delete → 409, FK rename propagation); FE `tsc` + `vite build` clean; `manage.py check` clean.

## [Refactor] Inline Skill/Location create reuses the Master Data validation engine
**Why** — the first cut of the inline "+ Add" dialogs hand-rolled their own trim/dedup checks, so validation could drift from the Master Data module. This makes the rules a **single source of truth**.
**What** — extracted the Master form's value-state + normalise-on-blur + live field validation + duplicate/inactive-duplicate/similar detection + payload assembly into one hook **`useMasterForm`** ([features/admin/useMasterForm.ts](frontend/src/features/admin/useMasterForm.ts)), driven entirely by the existing `config.ts` field rules + `lib/validation.ts`. **`ResourceForm`** (Admin Master Data) now consumes it. New generic **`MasterCreateDialog`** ([components/form/MasterCreateDialog.tsx](frontend/src/components/form/MasterCreateDialog.tsx)) — create-only, status forced **Active**, no edit/delete/reactivate — also consumes it, parameterised by a config key (`"skills"` / `"locations"`). The bespoke `SkillCreateDialog` / `LocationCreateDialog` and the `useCreateSkill`/`useCreateLocation` hooks were **removed**.
**Result** — the inline Add-Skill / Add-Location dialogs now apply the *identical* rules to the Master screens: trim + collapse spacing, the same Title-Case / canonical tech-term casing (`sql`→`SQL`, `node.js`→`Node.js`, …), reject empty / digits-only / symbols-only / invalid-charset values (`C++`, `C#`, `.NET` etc. allowed via the `skill`/`label` charset), case-/space-insensitive duplicate prevention (skill name; city+state+country), and the **same error messages**. Backend already routed both paths through `MasterDataViewSet` + `core/validation.py`, so the server enforced parity already; this aligns the client. A future rule change in `config.ts`/`validation.ts` now applies to every form at once.
**Permissions unchanged** — HM create-only via `CanManageReferenceData`; the "+ Add" trigger stays role-gated (ADM/HM); HM never sees edit/delete/activate/deactivate. New record auto-selected on the Requirement form, no refresh.
**Verified** — 82 backend tests (incl. new parity tests: HM inline-created skill `"  go   lang "`→`"Go Lang"`; case/space-insensitive HM duplicate → 400) + FE `tsc`/build pass.

## [Requirements] Inline creation of Skills & Locations (role-gated)
**What** — a Hiring Manager (or Admin) can now create a missing **Skill** or **Location** without leaving the **New Requirement** form. Each dropdown grows a role-gated **"+ Add new …"** action that opens a small modal; on save the new record is created, appended to the cache, auto-selected, and the form's other fields are untouched (no page refresh).
**Permissions** — new `CanManageReferenceData` ([authentication/permissions.py](backend/authentication/permissions.py)) applied to `SkillMasterViewSet` + `LocationMasterViewSet`: read → any authenticated; **create (POST) → ADM or HM**; **edit/delete → ADM only**. All other masters stay `IsAdminOrReadOnly`. So HM gets create-only inline access; curating/removing master data is still Admin-only via the Master module.
**Frontend** — new `SkillCreateDialog` (Skill Name required, Domain optional, Status = Active) and `LocationCreateDialog` (City required, State via `StateSelect` required, Country via `CountrySelect` default India, Status = Active), both with client-side case-insensitive duplicate guards (skill name; city+state+country), loading state and success/error toasts. New searchable `LocationSelect` (single-select with the role-gated footer) replaces the plain location `FormSelect` on the Requirement form. The "+ Add" footer is gated by `useAuth()` role (ADM/HM) so recruiters using the shared `SkillMultiSelect` on the Candidate form don't see it. New mutations `useCreateSkill`/`useCreateLocation` (`lib/lookups`) `setQueryData`-append + invalidate `["master"]` so every dropdown stays consistent.
**Verified** — 12 security tests pass incl. HM-can-create-skill/location, HM-cannot-edit-skill, HM-cannot-delete-location, REC-cannot-create-location; FE `tsc` + build pass; `manage.py check` clean. No schema change.

## [Skills] Reusable master-sourced multi-select
**What** — one reusable searchable **`SkillMultiSelect`** ([components/form/SkillMultiSelect.tsx](frontend/src/components/form/SkillMultiSelect.tsx)) sourced entirely from the Skills Master — no hardcoded lists. Type-to-filter (case-insensitive), keyboard nav (↑/↓/Enter/Esc/Backspace), removable chips, clear-all, duplicate-proof, optional `max`, alphabetical, accessible.
**Data/caching/refresh (already in place, now consumed)** — `useSkills` (`lib/lookups`) fetches **active only** (`?is_active=true`), is cached (5-min staleTime), and is auto-invalidated when an admin creates/edits/activates/deactivates a skill (master mutations invalidate `["master"]`) → every dropdown updates on the next fetch with no code change.
**Wired into** — **Requirement Create** (replaced the three single-select skill slots with one multi-select capped at 3 → mapped to `skill1/2/3`) and **Candidate Create** (new skills field → `skill_ids`, which the write serializer already supports; coexists with the "tag to requirement" inheritance).
**Scope note** — these are the only forms in the app that capture skills; Candidate/Requirement *Edit*, User/Recruiter/HM *Profile* screens don't exist yet (and `user_master` has no skills column), so there was nothing to convert there — the component is ready to drop into them when built.
**No backend/schema change.** Verified: candidate create with `skill_ids` tags the candidate (confirmed via the detail endpoint); requirement skills still map to skill1/2/3; `tsc` + build pass.

## [Master Data] Standardized Country / State (UT) dropdowns
**What** — replaced the free-text Country/State fields on the Location master with reusable, shared-list dropdowns. (Location master is the only form that captures state/country directly — every other form picks a location via the Location FK, so they inherit the standardization.)
**Shared data** — `lib/geo.ts` holds `COUNTRIES` (`["India"]` + `DEFAULT_COUNTRY`) and the 36 alphabetical `INDIAN_STATES` (states + UTs). Single source; no per-form hardcoding.
**Reusable components** — `Combobox` ([components/ui/combobox.tsx](frontend/src/components/ui/combobox.tsx), dependency-free searchable single-select: type-to-filter, ↑/↓/Enter/Esc, click-outside, shows legacy values not in the list), `CountrySelect` (defaults India, disabled while only one country — add to `COUNTRIES` to enable more) and `StateSelect` (`Combobox` over `INDIAN_STATES`, placeholder "Select State / Union Territory"). New config field types `country`/`state` render them in `ResourceForm`.
**Backend** — `location_master` state/country are now controlled-vocabulary, so they're trimmed-only (no `place` char-rule / strict-Title-Case that rejected official names like `Delhi (NCT)`); `city` stays validated + title-cased. No schema change.
**Validation/UX** — Country defaults to India; State stays required; values stored as strings; create/edit/search/display unchanged for existing rows. Styling matches the design system.
**Verified** — official state names (Delhi (NCT), Jammu and Kashmir, Dadra and Nagar Haveli and Daman and Diu…) accepted; `city` still rejects bad input; 75 backend tests + FE `tsc`/build pass.

## [Fix/Security] Verify session with backend before trusting it
**Root cause** — `AuthContext` restored `user`+`token` from `localStorage` and marked the session authenticated **without verifying the token**, so the app opened straight to the Dashboard (which then errored when the backend was down). A token's mere presence was treated as proof of auth.
**Fix** — added `GET /api/auth/me/` ([authentication/views.py](backend/authentication/views.py), any authenticated role) that validates the JWT and returns the current user. On startup `AuthContext` now sends the stored token to `/auth/me/` and only marks the session authenticated if it succeeds; on **401, network error, or timeout** it clears storage and stays logged out → the app lands on **Login**. `LoginPage` redirects an already-verified session to `/`.
**Result** — root `/` shows Login unless a backend-verified session exists; protected routes gated by `ProtectedRoute` (waits for the check); logout/invalid/expired/offline all end at Login. During the check `ProtectedRoute` shows the branded `PageLoader` (new `fullScreen` variant) instead of a blank screen.
**Verified** — 75 backend tests pass (`/auth/me/`: 200 with user for valid token, 401/403 without); FE `tsc` + build pass.

## [Candidates] Candidate Details drawer — UX refinement
**What** — denser, more professional drawer that handles sparse demo data gracefully (UI-only; no backend/API/logic changes).
- **Collapsible sections** (lightweight, remember open/closed while the drawer is mounted): **Activity timeline** expanded (now the primary content), Résumé + Requirement history collapsed, each with a count/PDF chip in its header.
- **Compact empty states** — résumé and requirement-history empties are now one-line messages, not large bordered boxes; the PDF viewer only renders when a file exists.
- **Richer header metadata** not duplicated from the table: Created on, Created by, total activities, total mappings.
- **Improved timeline** — coloured per-event markers, aligned title/timestamp, tighter spacing and typography.
- Reduced section/footer whitespace; layout structured so future sections (notes, communications, attachments) drop in without redesign.
**Verified** — `tsc` + build pass. No backend touched.

## [Candidates] Candidate Details drawer
**What** — clicking a candidate row opens a responsive right-side drawer with the info recruiters need before deciding, without leaving the Candidates page (no duplication of the table columns).
**Backend (read-only, no schema change)** — two `@action`s on `CandidateViewSet` ([candidates/views.py](backend/candidates/views.py)): `GET /api/candidates/{id}/detail/` returns a composite payload (candidate via the existing serializer + résumé metadata + **requirement history** from `JdCvMapping` + an **activity timeline** merged from candidate creation, `candidate_interaction` and `communication_log`); `GET /api/candidates/{id}/resume/` streams the active `cv_document` file (`FileResponse`, 404 when no file on disk). `available` flags whether the file physically exists (seed CVs are metadata-only → UI shows an empty state).
**Frontend** — new reusable **`Sheet`** primitive ([components/ui/sheet.tsx](frontend/src/components/ui/sheet.tsx), Radix-based right drawer with slide animation) and **`CandidateDrawer`** ([features/candidates/CandidateDrawer.tsx](frontend/src/features/candidates/CandidateDrawer.tsx)): compact header (name/CV ID/status), embedded PDF preview (authed blob via object URL) + Download, requirement history, timeline, and an Actions footer (Download · **Add to Requirement** entry-point only → toast · Close). Loading/empty/error states throughout. `DataTable` gained an optional `onRowClick`; rows on the Candidates page open the drawer. Drawer is built to extend later (notes, activity, Add-to-Requirement).
**Non-goals respected** — no candidate editing, no notes persistence, no pipeline-status editing, no Add-to-Requirement workflow yet.
**Verified** — detail payload (candidate + history + timeline) over the stack; résumé 404 → empty state; 73 backend tests pass; OpenAPI schema clean; FE `tsc` + build pass.

## [Pipeline] Server-side pagination for the review pool
**Why** — replaced the temporary `page_size=100` fetch so the review pool scales as the candidate repository grows.
**Backend** — `NewCvListView` ([pipeline/views.py](backend/pipeline/views.py)) adds DRF `SearchFilter` (`?search=` over name/email/mobile/cv_serial), applied **after** the `matched_skills` annotation + relevance ordering and **before** pagination (default `StandardResultsSetPagination`, 20/page). So the server computes relevance, then searches, then pages.
**Frontend** — `DataTable` ([components/DataTable.tsx](frontend/src/components/DataTable.tsx)) gained an **opt-in server mode** (`serverPagination` + controlled `search` props) using TanStack's `manualPagination`/`manualFiltering`; client-side screens are unchanged when the props are omitted. `useNewCvs(reqId, page, search)` is now paged + searched with `keepPreviousData`; `PipelinePage` drives `page` + a 300 ms-debounced `search`, resetting to page 1 on requirement/search change.
**Verified** — over HTTP: 43-row pool returns 20/20/3 across pages with correct `next` links, pages disjoint, relevance preserved across page boundaries, and `search` spans the whole pool (not just one page); 70 backend tests + FE `tsc`/build pass.

## [Pipeline] Skill-match score in the review pool
**Why** — the pool now lists every usable candidate (reuse), so the most relevant ones need surfacing without re-adding a hard filter.
**Backend** — `new_cv_candidates_for_requirement` ([pipeline/services.py](backend/pipeline/services.py)) annotates each candidate with `matched_skills` (count of the requirement's skills they hold, via `Count(..., filter=Q(...))`) and orders **best-match-first**. New `ReviewPoolCandidateSerializer` ([pipeline/serializers.py](backend/pipeline/serializers.py)) exposes `matched_skills`, `required_skills` (from view context), and `skill_match_pct`; `NewCvListView` passes the requirement's skill count in context.
**Frontend** — review table gains a **Match** column (`67%` badge — green ≥67 / amber ≥34 / muted — plus `2/3 skills`), sortable; `useNewCvs` now requests `page_size=100` so the **entire** reusable pool is reachable (the table paginates it). Match is a *ranking* signal only — the full pool remains accessible.
**Verified** — over HTTP: 100% matches sorted above 33%, score = matched/required, New CV + Saved both present, total pool (43) fully returned; 70 backend tests + FE `tsc`/build pass.

## [Pipeline] Review pool reuses existing candidates
**Why** — the "New CVs to review" pool only showed global-status `NEW_CV` candidates, so once a candidate was shortlisted anywhere (global → `SAVED`) they vanished from every requirement's pool, blocking reuse — even though `JdCvMapping` supports many mappings per candidate.
**Change** — `new_cv_candidates_for_requirement` ([pipeline/services.py](backend/pipeline/services.py)) now returns **every usable candidate** (global status `NEW_CV` **or** `SAVED`; Fake / Possible Duplicate excluded) that is **not already mapped to the selected requirement**. The hard skill-match filter was removed (skills are still prefetched for display); rule is now "show every usable candidate not already associated with this requirement." Frontend copy updated (heading "Candidates to review"; empty-state text) in [PipelinePage.tsx](frontend/src/features/pipeline/PipelinePage.tsx).
**No schema / API / permission changes** — `review_candidate` (`get_or_create` + `unique_together(req, candidate)`) still prevents duplicate mappings; recruiter scoping and `IsRecruiterOrAdmin` unchanged.
**Verified** — pool now NEW_CV+SAVED, excludes already-mapped & Fake; a Saved candidate from another requirement appears for reuse; re-shortlisting yields exactly one mapping (rolled-back test); 70 backend tests pass; FE `tsc` + build pass.

## [Master Data] Field-specific validation rules (per request)
Extended the shared validators (`core/validation.py` + `lib/validation.ts`) — no new layer, other masters untouched. Enforced on **create + edit, frontend + backend**.
- **Mobile** (user + client-manager): trimmed before validation; must be exactly 10 numeric digits (`^[6-9]\d{9}$`) — alphabets/spaces/symbols rejected with a clear message.
- **Location** name (city/state/country): only letters, spaces, `'` and `-` (numbers/symbols rejected); auto-normalised to **strict Title Case** via a new `title_strict` mode that fixes inconsistent capitalisation instead of erroring (`india`→`India`, `mUMBAI`→`Mumbai`, `o'fallon`→`O'Fallon`, `dadra-nagar haveli`→`Dadra-Nagar Haveli`).
- **Priority** name: letters + spaces only (`alpha` kind).
- **Work Mode / Requirement Type / Requirement Status** names: letters, spaces, `-` and `&` only (`alphaamp` kind).
**Verified** — `tsc` + build pass; backend suite **70 passing** (new cases for strict Title Case + per-field character rules); HTTP create/edit confirmed (e.g. `INdia town`→`India Town`; `High-Low`, `Work / Home`, `Bad@Status`, `Pune1` → 400; `  9820011099  `→`9820011099`).

## [Fix] Role dropdown empty in New User modal
**Root cause** — dropdowns request `?is_active=true` (active-only), but `MasterDataViewSet.get_queryset` applied that filter unconditionally; `role_master` has no `is_active` column, so `/roles/?is_active=true` raised a `FieldError` (500) and the Role select rendered with no options (appeared "not selectable"). Not a z-index/disabled issue — the Select is portaled above the modal already.
**Fix** — guard the filter with `_has_field("is_active")` so masters without that column (role_master) simply skip it. `/roles/?is_active=true` now returns the 3 active roles; 53 tests pass.

## [Polish] Code-splitting — smaller initial bundle
**Why** — the app shipped as one ~1 MB (≈328 KB gzip) JS file with a build size warning. Split it so heavy libraries load on demand.
**Changed** — routes are now `React.lazy` + `Suspense` (per-page chunks, with a shared `PageLoader`; an inner Suspense in `AppShell` keeps the sidebar/topbar during page transitions). `vite.config.ts` adds a `manualChunks` function (rolldown requires a function) splitting `recharts`→`charts`, `@tanstack/react-table`→`table`, `@tanstack/react-query`→`query`, RHF+Zod→`forms`, React/router/dom→`react-vendor`.
**Result** — initial (login) load ≈140 KB gzip; Recharts (`charts`, 110 KB gzip) deferred to Dashboard/Pipeline; each page chunk 4–23 KB. Build warning gone; `tsc` + build pass.

## [Master Data] Canonical Title-Case normalization
**Why** — extend the existing master-data normalization so saved values are consistently cased without mangling technical terms. Reuses the same `core/validation.py` (backend) + `lib/validation.ts` (frontend) utilities — no new validation layer.
**Added** — general text fields (Skill, Location, Source, Department, Status names, etc.) now normalize to **Title Case**, with a shared **`CANONICAL` map** of technical terms that wins over Title Case (`github`→`GitHub`, `sql`→`SQL`, `power bi`→`Power BI`, `node.js`→`Node.js`, `ui/ux`→`UI/UX`, …). A smarter title-caser preserves acronyms and intentional internal capitals (`HCL`, `LTIMindtree`, `ReactJS`, `iOS`, `OK`, `JD`). Codes stay UPPER; descriptions/body untouched.
**Duplicate detection** — unchanged and already normalization-aware: comparison is case-/space-insensitive on both incoming input and existing DB values, enforced centrally in `MasterDataViewSet` for create **and** update.
**Tests** — new `tests/test_validation.py` (37 cases: canonical/Title-Case normalization, duplicate-key equivalence, name-format rejection). Suite now 53 passing.
**Verified** — over HTTP: messy `  quantum   computing ` → `Quantum Computing`; `graphql` → `GraphQL`; case/space variants blocked on create; an update that would create a duplicate is rejected. `tsc` + build pass.

## [UI/UX] Donut tooltip — portal to body (fixes sidebar clipping)
**Root cause** — the tooltip was clipped because it's a DOM descendant of the dashboard's scrolling `<main className="overflow-y-auto">` (and the AppShell root `overflow-hidden`); `allowEscapeViewBox` only escapes the SVG viewBox, not these HTML overflow ancestors, so a left-anchored tooltip got cut off / hidden behind the sidebar. `z-index` can't help when an `overflow` ancestor clips.
**Fix (Recharts best practice, no CSS hacks)** — a custom `Tooltip content` that renders via **`ReactDOM.createPortal(..., document.body)`** with `position: fixed`, so it's no longer inside the clipped containers. Recharts still owns the active state + cursor `coordinate`; we convert that (+ the chart box's `getBoundingClientRect`) to viewport coords, nudge off the cursor, and flip near screen edges. `zIndex:1000` (above the `z-30` topbar), `pointerEvents:none`. Active-slice enlarge (`activeShape`) and centre total preserved; responsive. `tsc` + build pass.

## [UI/UX] Donut tooltip — positioned outside the donut (no centre overlap)
**Why** — the hover tooltip covered the centre "Total" label. Fixed the Recharts way (no CSS hacks): a custom `Tooltip content` plus a **dynamic `position`** computed from the hovered slice's geometry (`onMouseEnter` → slice `cx/cy`, start/end angle → a point just beyond the outer radius, anchored left/right of the slice so it never crosses the centre). Added `allowEscapeViewBox={{x:true,y:true}}`, `wrapperStyle` (`zIndex`, `pointerEvents:none`), and `overflow-visible` on the chart box so the escaped tooltip isn't clipped. Centre total stays permanently visible; active slice still enlarges (`activeShape` + `Sector`); chart stays responsive. `tsc` + build pass.

## [UI/UX] Donut chart — readability polish
**Requirements-by-status donut** refined to enterprise standard: the legend now shows **status name + count only** (percentages removed); names no longer truncate in practice (wider legend cells, percentage column dropped) and any clipped name shows in full on hover (`title`). Percentages moved into a **professional hover tooltip** (status name + Count + Percentage, Material card styling). The hovered slice **enlarges** for active emphasis (Recharts v3 `activeShape` + `Sector`). Centre total unchanged; layout stays responsive without legend overlap. `tsc` + build pass.

## [UI/UX] Responsive dialogs + chart-overflow fixes
**Dialogs (fixed once, in the `Dialog` primitive → applies to all 9 modals)** — `DialogContent` is now a flex column capped at `max-h-[90vh]` with a responsive width (`w-[calc(100%-2rem)]` + per-modal `max-w`), so a modal never spills past the viewport. New **`DialogBody`** holds the scrollable middle; `DialogHeader`/`DialogFooter` are `shrink-0` and stay visible (footer gets a divider). Every modal (Resource, Requirement, Candidate, BulkUpload, JdCompose, Schedule, Reason, Assign) was wrapped in `DialogBody`; the long form dialogs now scroll the body only with Save/Cancel always reachable.
**Donut chart** — the "Requirements by status" legend no longer overflows the card: the legend flexes within the space beside the donut (`flex-1 min-w-0`, was `w-full`) and long labels truncate; donut radius trimmed to fit. Counts and percentages stay inside the card at all widths/zoom.
**Responsiveness** — verified content stays within cards/tables/forms (tables already scroll via `overflow-x-auto`); relative units + `min-w-0`/truncate keep the layout clean at 100/125/150% zoom.
**Verified** — `tsc --noEmit` clean; production build passes.

## [Master Data] Enterprise CRUD hardening (validation, dedupe, soft/permanent delete, audit, locking)
**Why** — invalid rows (e.g. `N--ashik`, `@@@@`, numeric-only) and case-/space-variant duplicates could be saved, and delete was an unconditional hard delete. Brought every master screen up to Workday/Greenhouse-grade CRUD, with the logic centralised so all 12 masters behave identically.
**Migration `0004`** — added `updated_by`/`updated_on` to the 9 masters that lacked them, so **every** master now records Created By/On + Updated By/On and supports optimistic locking.
**Backend (centralised in `core/validation.py` + `MasterDataViewSet`)**
- **Normalisation** — trim, collapse internal whitespace, strip invisible/zero-width chars, NFKC; codes upper-cased, places title-cased.
- **Field validation** — per-field "kind" rules (`place`/`person`/`skill`/`handle`/`label`/`email`/`phone`/`code`): reject no-letter values, random symbols, leading/trailing & doubled & spaced hyphens, bad email/phone, and over-length.
- **Duplicate prevention** — case-/space-insensitive on unique fields & unique-together groups (create **and** edit); DRF's stock unique validators stripped so this is the single authority.
- **Soft delete** (default `DELETE` → deactivate) **and Permanent delete** (`DELETE /{id}/permanent/`, blocked with a clear 409 when referenced); `GET /{id}/references/` reports what points at a row.
- **Reactivation** — creating something that matches an **inactive** row returns `409 {code: inactive_duplicate, record}` so the UI can offer reactivation.
- **Optimistic locking** — edits send `expected_updated_on`; a stale token is rejected.
- **Audit** — `created_by/on` + `updated_by/on` filled automatically; `is_active` defaults to true.
- Lookups accept `?is_active=true` so dropdowns hide inactive rows.
**Frontend (centralised in `lib/validation.ts`, mirrors the backend)**
- `ResourceForm` rebuilt: live per-field validation, normalisation on blur, inline errors + invalid-field highlight, **Save disabled until valid**, instant duplicate block, fuzzy "similar record" warnings (Dice coefficient), and an inactive-duplicate **Reactivate** prompt.
- `MasterDataPage` delete dialog now offers **Deactivate** vs **Delete permanently** (the latter disabled + explained when the record is referenced, using the references probe). App-wide lookups + admin selects request active-only.
**Verified** — invalid names rejected (HTTP 400), case/space duplicates blocked, soft/permanent delete + referential block, inactive→reactivate, optimistic-lock conflict, audit stamps, and active-only dropdowns all confirmed over HTTP; 16 pytest pass; frontend `tsc` + build pass.

## [Dashboard] Recruiter Workload chart
**Backend** — `dashboard_service._recruiter_workload()` adds a `recruiter_workload` section to the **admin** payload: per recruiter `{recruiter, requirements, candidates}` (active requirements assigned vs. candidates in their pipeline), sorted by heaviest load, idle recruiters omitted. Read-only ORM aggregation; no schema change.
**Frontend** — new reusable **`RecruiterWorkloadChart`** (grouped vertical bars: Requirements in blue, Candidates in teal; value labels + legend). Dashboard charts re-laid-out for admin: donut (Requirements by status) + Recruiter Workload side-by-side on top, Pipeline-by-stage bar full-width below.
**Verified** — aggregation returns correct per-recruiter counts over HTTP/ORM (Rajeev 4/12, Sneha 3/9, Arjun 2/5; idle recruiter dropped); Django check + 16 pytest pass; frontend `tsc` + build pass.

## [Dashboard UX] Enterprise chart redesign (frontend only)
**Why** — the dashboard charts were single-colour, cramped, and wrapped long labels; many pipeline stages were squeezed into a small fixed-height card. No business logic, API, or chart data changed — purely presentation.
**Added** — a **semantic chart palette** (`lib/chart.ts` `STATUS_COLOR` + `statusColor()`, keyed by status display-names; documented in DESIGN_SYSTEM §12) so every requirement/pipeline stage has a distinct meaningful hue. New reusable **`DonutChart`** (centre total + text legend with counts/%).
**Changed**
- **Requirements by status → donut** (was a bar); **Pipeline by stage → horizontal bar** with semantic per-bar colour, value labels at bar end, rounded corners, subtle dashed grid, proper bar spacing, and **dynamic height (44px/row)** so many stages never compress.
- `ChartCard` no longer forces a fixed height (optional subtitle, flexible body); charts size themselves. Dashboard charts moved to their own top-aligned grid with responsive column spans per role (admin sees both; HM donut-only; recruiter full-width bar).
- Accessibility: meaning never depends on colour alone (text labels + value labels + legend + tooltips).
**Verified** — `tsc --noEmit` clean; production build passes.

## [Demo data] Realistic Indian seed dataset
**Added** — `python manage.py seed_demo`: an idempotent management command that populates the full recruiter workflow with **authentic Indian business data** — real names, well-known IT employers (TCS, Infosys, Wipro, HCL, Tech Mahindra, Cognizant, Capgemini, Accenture, LTIMindtree, Persistent), Indian cities, name-based professional emails, valid 10-digit mobiles, believable experience/CTC/notice/education, and résumé-style CV filenames (e.g. `Rahul_Sharma_Resume.pdf`). No placeholder/dummy values.
**Coverage** — 48 candidates (22 in the New-CV review pool), 9 requirements with real titles (Senior Java Developer, React Developer, Data Analyst, DevOps Engineer, …), and a 26-row pipeline spread across **every stage** — 9 Shortlisted (so JD compose/preview is populated), JD-sent (with rendered `communication_log` entries via the live template path), scheduled screenings, and outcomes. Master rows are upserted by natural key; transactional rows + the old `ZZ Test Client`/`ZZ POC` placeholders are cleared and rebuilt each run.
**Verified** — review pool, JD preview, tracker, and role dashboards all return realistic data over HTTP; 16 pytest tests still pass.

## [UC4 UX] JD email — admin template, compose/preview & tracker
**Why** — the JD email body was hardcoded in `send_jd_emails`. It is now **configuration as data**: an admin-editable template, with one render path powering both the preview and the actual send ("what you preview is what's sent").
**Schema** (`database/migrations/0003_email_template.sql`) — `email_template_master` (`template_code` unique, `subject`, `body`, `is_active`, audit) seeded with a `JD_EMAIL` template. Placeholders: `{candidate_name} {role} {client} {location} {exp} {ctc} {notice} {skills} {sender}`.
**Backend**
- Master endpoint `/api/email-templates/` (admin-writable via `MasterDataViewSet`).
- `pipeline/services`: `get_jd_template` + `_build_jd_context` + `_render` → `render_jd_email`; `send_jd_emails` refactored to render from the template (no more inline subject/body); `preview_jd_emails` and `communications_for_requirement`.
- New endpoints `POST /api/pipeline/jd-preview/` (render without sending) and `GET /api/pipeline/communications/?requirement=` (send-log tracker). A missing/inactive `JD_EMAIL` template → `400` with a clear message.
**Frontend**
- Admin framework gained a **`textarea`** field type (+ field `hint`); **Email Templates** resource added to Master Data.
- **`JdComposeDialog`** — recipient checklist (shortlisted candidates) + live server-rendered preview + send; every JD send (single row or bulk) now flows through it. **`JdTracker`** tab on the pipeline board lists every send attempt (status/sent-by/time).
**Verified** — `email-templates` lists `JD_EMAIL` (admin); `jd-preview` renders a recipient over HTTP ("Dear Arjun Sharma…", full subject); `communications` returns the log; full send path writes `communication_log` (`SENT`) and advances the mapping; frontend typecheck + production build pass.

## [UC0b] Admin — User management
**Backend** — `UserWriteSerializer` (write-only `password` → `make_password`; required on create, blank-keeps-current on update). `UserMasterViewSet.get_serializer_class` uses it for create/update; reads still hide the hash. Admin-only (`IsAdminOrReadOnly`).
**Frontend** — added a `password` field type to the admin framework (required on create, "leave blank to keep current" on edit); **Users** resource (full name, username, email, mobile, **role** select, password) at the top of Master Data.
**Verified** — admin creates a user (role HM) → `201`, hash not exposed; the new user **logs in successfully** (password hashed); recruiter create → `403`. Build passes.
**Milestone** — the full Admin Master-Data area (UC0) is complete: 14 master tables manageable, including users + roles.

## [Frontend UC0c] Admin — clients, client-managers & workflow statuses
**Added** to the admin Master Data screen: **Requirement Status, CV Status, Clients, Client Managers** (alongside the existing lookups — 13 master tables now manageable).
**Framework** — added a **`select` field type** (`ResourceSelectField`, fetches its own options) so the dependent **client → client-manager** relationship works; backend `ClientManagerMasterSerializer` now returns `client_name`.
**Verified** — all four lists load; client create `201`; dependent client-manager create `201` with `client_name` resolved; build passes.
**Guidance** — for `cv_status`/`req_status`, admins can freely **add** statuses and rename **display names**; the `status_code` is what the workflow logic references, so renaming an existing code can affect behaviour.

## [Migration 0002] Workflow masters (scope-aligned)
**Schema** (`database/migrations/0002_workflow_masters.sql`)
- **Added** `screening_mode_master` (Telephonic, Video) and `rejection_reason_master` (10 seeded reasons).
- **Replaced** the misnamed `interview_round_master` → **dropped** it (our process is single-screening; the table was unused).
- `jd_cv_mapping` **+** nullable FKs `screening_mode_id`, `rejection_reason_id`.
- `cv_status_master`: display "Not Relevant" → **"Not Suitable"** (aligns with workflow language; codes unchanged).
**Backend** — models swapped (`ScreeningModeMaster`, `RejectionReasonMaster`); admin endpoints `/api/screening-modes/`, `/api/rejection-reasons/` (replacing `/interview-rounds/`). Pipeline `review` accepts `rejection_reason` (Not-Suitable); `transition` accepts `screening_mode` (scheduling) + `rejection_reason` (Dropped/No-Response/Rejected/Fake).
**Frontend** — `ReasonDialog` prompts a structured reason on negative review/transition; `ScheduleDialog` captures screening mode; both masters added to the admin framework.
**Verified** — masters seed + serve; `interview-rounds` → 404; Not-Suitable/Rejected store reason; screening stores mode; build passes.
**Scope note** — Offer/joining/interview-status masters intentionally **not** added (workflow ends at "OK to Proceed").

## [Frontend UC0a] Admin — Master Data management
**Added**
- **Config-driven master-data CRUD framework** (`features/admin/`): a `RESOURCES` registry (endpoint, columns, fields) drives a generic `MasterDataPage` (left sub-nav + `DataTable`) + `ResourceForm` (add/edit) + delete-confirm. Adding a table = one config entry.
- Covers **Skills, Locations, Sources, Notice Periods, Work Modes, Priorities, Requirement Types** — add / edit / activate-deactivate / delete (delete fails gracefully if the row is referenced → toast suggests deactivating).
- Admin-only route `/admin` (role-gated via `ProtectedRoute allow={["ADM"]}`); sidebar "Master Data" activated for Admin.
**Verified** — admin CREATE `201`, PATCH `200`, DELETE `204`; recruiter write `403`; build passes.
**Next (UC0b)** — User management (add user + assign role + activate) — needs a backend create-user-with-password endpoint.

## [Frontend F5b] Pipeline — Send JD + screening (UC4–UC5)
**Added**
- `Tabs` primitive (Radix). `StageBoard` on the Pipeline page with stage tabs **Shortlisted → JD Sent → To Schedule → Scheduled**, each loading `jd_cv_mapping` rows for that status with contextual actions.
- Actions: **Send JD** (`/pipeline/send-jd/` → JD Email Sent); **respond** (Move to screening / No response / Drop); **schedule** via `ScheduleDialog` (datetime-local → Screening Scheduled); **outcome** (OK to Proceed / Reject / Mark fake). Hooks `useMappings`, `useSendJd`, `useTransition` (state-machine on the backend).
**Verified** — full chain on req 33: Shortlisted → Send JD → Schedule (Jul 1 10:30) → OK to Proceed; build passes; modules transform.
**Milestone** — the complete UC0–UC5 recruitment workflow is now usable in the UI.

## [Frontend F5a] Pipeline — review New_CVs (UC3)
**Added**
- `features/pipeline/`: `PipelinePage` with a **requirement picker** (recruiter's assigned reqs; admin sees all), a requirement summary card, and a table of **skill-matched New_CV candidates**.
- Per-row **Review** action (dropdown): Shortlist / Not suitable / Save for later / Mark fake → `POST /pipeline/review/`; updates the pipeline + dashboard. `useNewCvs` + `useReviewCandidate`.
- Route `/pipeline`; sidebar "Pipeline" activated for Recruiter.
**Verified** — seeded New_CV → appeared in pool (1) → Shortlist → candidate `SAVED` + mapping `SHORTLISTED`, pool → 0; build passes; modules transform.
**Next (F5b)** — Send JD (UC4) + screening transitions (UC5).

## [Frontend F4b] Excel bulk upload (UC2)
**Added**
- `BulkUploadDialog`: download `.xlsx` template, pick a file, optionally tag to a requirement, upload → shows the **per-row report** (created / updated / possible-duplicates / errors / warnings). "Bulk upload" button on the Candidates page (REC/Admin).
- `useBulkUpload` (multipart `FormData`) + `downloadCandidateTemplate` (blob download).
**Fixed**
- API client no longer hardcodes `Content-Type: application/json` — axios now sets it per request (JSON for objects, multipart-with-boundary for uploads).
- Dev CORS widened to `localhost`/`127.0.0.1` ports **5173–5175** (Vite picks the next free port; this stops "cannot reach server" when it lands on 5174).
**Verified** — template → 200 (xlsx); upload of a 5-row sheet → report (3 updated, 1 possible-dup, 1 error, 1 warning); build passes; module transforms.

## [Frontend F4a] Candidates list + add (UC2)
**Added**
- **Candidates list** (`features/candidates/`): DataTable (CV, name+email, mobile, exp range, location, skills, status `Badge`, added date), global search + client-side **skill filter**.
- **Add candidate** form (`CandidateFormDialog`, RHF+Zod) → `POST /candidates/`; handles **201 created / 200 updated / 409 possible-duplicate** (duplicate shows the existing record in a toast). Optional "tag to requirement" to inherit its skills. Add gated to REC/Admin.
- Route `/candidates`; sidebar link activated for REC + Admin.
**Refactor (DRY)** — consolidated all master-data lookup hooks into shared `lib/lookups.ts` (+ sources, work-modes) and extracted a shared `components/form/FormSelect`; requirements repointed at both, duplicates deleted. `Paginated<T>` moved to `lib/types.ts`.
**Verified** — list loads; create → 201 (CV-000005); duplicate → 409; modules transform; build passes.
**Next (F4b)** — Excel bulk upload + per-row report + template download.

## [Frontend F3b] Requirements create + assign (UC1 write)
**Backend** — `UserMasterSerializer` now exposes read-only `role_code`/`role_name` (so the recruiter picker can filter without an extra roles lookup).
**Frontend**
- Primitives: `Dialog`, `Select`, `Textarea` (Radix), `Toaster` (sonner) wired in `main.tsx`.
- **New requirement** form (`RequirementFormDialog`, React Hook Form + Zod): dependent **client → client-manager** select, skills/dates/exp-range validation, `POST /requirements/` → toast + query invalidation.
- **Assign** row action (`AssignDialog`): recruiter picker (filtered by `role_code === REC`) → `POST /requirements/{id}/assign/`.
- Create/Assign visible to **HM/Admin only** (role-gated via `useAuth`). Columns refactored to `buildRequirementColumns({ onAssign })`.
**Verified** — form-shaped `POST` → `201` (REQ auto-number, skills tagged); assign → `200` (status Assigned); modules transform; build passes.

## [Frontend F3a] DataTable + Requirements list (UC1 read)
**Added**
- Reusable **`DataTable`** (TanStack Table, headless): global search, sortable headers, client-side pagination, column visibility, sticky header, row hover, loading skeletons, empty state.
- **Requirements list** (`features/requirements/`): `useRequirements` (TanStack Query, `page_size=100`), `requirementColumns` (tracker, role+client, type, recruiter/Unassigned, positions filled/open, status `Badge`, created date), `RequirementsPage`.
- Route `/requirements`; activated the sidebar "Requirements" link for all roles.
**Verified** — build passes; dev server serves; modules transform; endpoint returns requirements with correct fields.
**Note** — client-side table over `page_size=100` (fine for Phase 1 scale); switch to server-side pagination/sort when data grows.

## [Frontend F2b] Role dashboards + dashboard API
**Backend**
- `GET /api/dashboard/` is now **role-aware** (`admin_module/dashboard_service.build_dashboard`): KPIs, requirement/pipeline status breakdowns, recent requirements/candidates, upcoming screenings — scoped per role (ADM all · HM their requirements · REC their assigned reqs + uploads). Replaces the old flat counts.
**Frontend**
- Single role-aware `DashboardPage` (`features/dashboard/`) via **TanStack Query** (`useDashboard`); replaced the 3 per-role dashboard components (DRY).
- Bento grid: KPI `StatCard`s (icons), `ChartCard` + `StatusBarChart` (Recharts), recent-items list cards with status `Badge`s (via `statusVariant` map), loading skeletons.
- Helpers: `lib/chart.ts` (token-only palette), `lib/status.ts` (status→variant), `lib/format.ts` (dates).
**Verified** — build passes; dev server serves; dashboard endpoint returns correct per-role data for ADM/HM/REC.

## [Frontend F2a] AppShell + premium Login
**Added**
- Layout components: dark fixed `Sidebar` (role-aware nav, "Soon" markers for upcoming screens), sticky `Topbar` (avatar + user dropdown menu → sign out), `PageHeader`, and `AppShell` (sidebar + topbar + scrolling content).
- UI primitives: `Avatar`, `Checkbox`, `DropdownMenu` (Radix-based, design-system styled).
- Redesigned **Login** as a premium split-screen (brand story + highlights left, focused sign-in card right) using design tokens.
**Changed** — router now uses `AppShell`; removed dead `AppLayout`.
**Verified** — production build passes; dev server serves; shell/login/component modules transform without errors.

## [Frontend Design System] Enterprise design foundation
**Added**
- Design tokens (color/typography/spacing/radius/shadows/animation) per the enterprise palette (`#2563EB` primary, dark `#0F172A` sidebar, teal accent, semantic status colors) — `src/index.css` + `tailwind.config.js`; documented in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).
- **Inter Variable** font; `Badge` + `Skeleton` primitives (palette proof).
- Stack libraries wired: **TanStack Query** (`QueryClient` in `main.tsx`), React Hook Form, Zod, Recharts, `@fontsource-variable/inter`.
**Status** — design-system foundation built & building; layout + remaining component library presented as a spec **awaiting approval** before screen implementation.

## [Frontend F1] React foundation
**Added**
- `frontend/` — Vite + React + TypeScript, Tailwind v3, shadcn-style primitives (button/input/label/card) + `cn()` helper + `@`→`src` path alias.
- Axios API client (JWT injection, 401 → redirect to login), `AuthContext` (login/logout, session in `localStorage`), `ProtectedRoute` (auth + role guard).
- App shell (`AppLayout`: sidebar + topbar + logout), `LoginPage`, and role-based dashboards (Admin fetches `/dashboard/` stats; HM/Recruiter scaffolds).
- `.env` → `VITE_API_BASE_URL`.
**Verified** — production build (tsc + vite) passes; dev server serves SPA; cross-origin login from `localhost:5173` returns token with correct CORS header; entry module transforms without errors.

## [Hardening] Tests + API docs + security
**Added**
- **Tests** (`pytest` + `pytest-django`, 16 tests): requirement auto-numbering & assignment, candidate duplicate matrix & skill-tagging, pipeline state machine (legal/illegal/FAKE/datetime-required), and API permission/security checks. DB strategy: reuse existing DB + per-test rollback (managed=False). `requirements-dev.txt` added.
- **API docs:** `drf-spectacular` — OpenAPI schema at `/api/schema/`, Swagger UI at `/api/docs/`, ReDoc at `/api/redoc/`; Bearer-JWT auth scheme registered; APIViews annotated with `@extend_schema` (0 schema errors).
- **Login throttling:** `ScopedRateThrottle` on `/api/auth/login/` (rate via `LOGIN_THROTTLE_RATE`, default 10/min) — verified 429 after limit.
**Changed / Fixed**
- Master-data writes (`/api/roles/`, `/api/skills/`, …) locked to **ADM** via `IsAdminOrReadOnly` + a `MasterDataViewSet` base (reads stay open to any authenticated user).
- `UserMasterSerializer` no longer exposes `password_hash`.
- `USE_TZ = False` to match the DB's `timestamp without time zone` columns (removes naive/aware warnings).
- `UserMaster` list now ordered (deterministic pagination).

## [UC4–UC5] JD email + screening pipeline

## [UC4–UC5] JD email + screening pipeline
**Added**
- `GET /api/pipeline/mappings/?requirement=&status=` — load pipeline rows by stage.
- `POST /api/pipeline/send-jd/` (UC4) — emails the JD to SHORTLISTED candidates (console backend → real SMTP via env later), writes `communication_log`, advances to `JD_EMAIL_SENT`.
- `POST /api/pipeline/transition/` (UC5) — state-machine-guarded moves: `JD_EMAIL_SENT → Schedule_Screening/Dropped/No_Response`; `Schedule_Screening → Screening_Scheduled` (requires `screening_datetime`); `Screening_Scheduled → OK_to_Proceed/Rejected/Fake`. `FAKE` also flips the candidate's global status.
- `STAGE_TRANSITIONS` table rejects illegal jumps; all moves logged to `candidate_interaction`.
**Verified** — send-JD ×2 (emails rendered, 2 communication_log rows); happy path to OK_to_Proceed; FAKE branch flips global status; illegal transition rejected.

## [UC3] Recruiter reviews New_CV candidates
**Added**
- `pipeline/` app: `GET /api/pipeline/new-cvs/?requirement=`, `POST /api/pipeline/review/`.
- Review state machine: SHORTLISTED / NOT_SUITABLE → `jd_cv_mapping` + candidate→Saved; FAKE → candidate→Fake; SAVED → candidate→Saved.
- Data-scoped RBAC: recruiter limited to assigned requirements (admin bypass).
- `candidate_interaction` audit entry on every decision.
**Fixed**
- `JdCvMapping` reverse query used `cv_id`; corrected to `candidate_id`.
**Verified** — pool of 4 → decisions applied → pool reduced to 1; 403 on unassigned requirement.

## [UC2] Candidate management
**Added**
- `candidates/` app: manual create with §7 duplicate logic, Excel template download, Excel bulk import (per-row report), global search (`?search=`, `?skill=`, filters).
- CV-serial generation, skill tagging from requirement, status `New_CV`.
- Dependency `openpyxl==3.1.5`.
**Fixed**
- `is_willing_to_relocate` (no model default) defaulted to `False` in serializer.
**Verified** — create/update/possible-duplicate matrix; bulk report (created/updated/possible-dup/error/warning).

## [UC1] Requirement creation & assignment
**Added**
- `requirements/` app: CRUD + `POST /api/requirements/{id}/assign/`.
- Auto `Req_TrackerNo` / `JD_Serial_Number` (transaction + retry); default status New; HM auto-set.
- Permissions `IsHiringManagerOrAdmin`, `IsRecruiterOrAdmin`; demo users seeded (3 roles).
**Fixed**
- `is_active` (no model default) set in service to satisfy NOT NULL.
**Verified** — auto numbering + sequence; recruiter 403; assign flow; validations.

## [Foundation]
**Added**
- `.env`-driven settings (`python-dotenv`), `.env.example`, prod-hardening block.
- `core/` app: constants, pagination, exception envelope, audit mixin.
- Logging (console + rotating file).
**Fixed**
- `UserMaster.is_authenticated` / `is_anonymous` properties (all authed endpoints were 500ing).

## [Data Model] migration 0001_phase1_pipeline
**Added** — `jd_cv_mapping`, `candidate_skill`, `cv_document`, `candidate_interaction`, `communication_log`; `status_code` columns; `migrate_sql` command.
**Changed** — `requirement_tracker` experience → `exp_min`/`exp_max` (dropped `exp`); `+jd_serial_number`, `client_req_id`; `candidate_master +duplicate_of_cv_id`.
