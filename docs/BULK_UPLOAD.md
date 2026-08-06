# Bulk Candidate Upload — Excel-to-ATS Mapping

Single source of truth: the mentor-approved **Naukri "Candidate Details"** export.
Data lives in the **"Candidate Details"** sheet; the header row is **auto-detected**
(it is not row 1), and the **"Candidate insights"** analytics sheet plus blank /
decorative rows are ignored. Downloadable sample template: `GET /api/candidates/upload-template/`.

## Column → field mapping

| Excel column | → `candidate_master` field | Parsing / handling |
|---|---|---|
| # | — | ignored (row serial) |
| Candidate Name | `candidate_name` | trim; **required**; >100 chars → truncated (warning) |
| Resume Title | `additional_notes` | prefixed `"Resume title: …"` |
| Contact No. | `mobile` | digits only; strips `+91`/leading `0`; picks the **first** valid 10-digit number if a cell holds several (warning); **required + duplicate key** |
| Email | `email` | trim + lowercase; format-validated; **required** |
| Work Exp | `exp_min` = `exp_max` | `"7Y 7 M"` → `7.6` years; unparseable → blank (warning) |
| Annual Salary | `current_ctc_lpa` | `INR x.x L` → `x.x`; **`0.0 L` (undisclosed) → blank, NO warning**; `USD …`, unparseable, or out-of-range (>99999.99) → blank **with** warning |
| Current Location | `current_location` (FK) else `current_location_text` | resolve to Location Master; **unmapped kept as text (≤150) + warning** (never discarded) |
| Preferred Location | `preferred_location` (FK) + `additional_notes` | first value → FK; remaining → notes |
| Current Employer | `current_company` | trim; >100 → truncated (warning) |
| Designation | `current_designation` | trim; >120 → truncated (warning) |
| U.G. / P.G. / Post-P.G. Course | `highest_qualification` | highest present (Post-PG > PG > UG), Title-cased, ≤80 |
| Age/Date of Birth | `age_at_import` + `date_of_birth` | split `"32 y (09 Sep 1993)"`; **age is a snapshot, never recalculated**; DOB sanity-checked (below) |
| Postal Address | `postal_address` | trim; >255 → truncated (warning) |
| Comment 1–5 | `additional_notes` | non-empty concatenated with labels |
| Last Active | — | ignored (Naukri activity metric; no schema change) |

**Defaults for columns absent from the template:** `source` = the selected Source
(defaults to **"Naukri"** from Source Master, configurable — not hardcoded);
`is_willing_to_relocate` = `False`; `notice_period` / `work_mode` / `expected_ctc_lpa` blank.

**Header auto-detection:** the parser scans the first ~25 rows for a row that
contains the three required labels (Candidate Name, Contact No., Email), matching
on a normalized form (lower-case, punctuation → spaces) against a curated
header-alias map (`"Contact No."`, `"Mobile"`, `"Phone"`, … all map to `mobile`).
No fuzzy matching, so lookalikes such as "alternate email" are never mis-mapped.

## Location resolution

- **Literal-city-first, then alias-fallback.** The imported city is tried
  **as written** first, so a name that already exists in Location Master
  (e.g. `Gurugram`) is **never** rewritten away by the alias map. The alias
  canonical is only a fallback when the literal name isn't in the master.
- **Curated alias map** (normalized variant → canonical spelling; helps only when
  the canonical city exists in Location Master — **no auto-creation**):
  `bengaluru`/`blr`→**Bangalore**, `bombay`→**Mumbai**,
  `new delhi`/`delhi ncr`/`ncr`→**Delhi**, **`gurugram`+`gurgaon`→Gurugram**,
  `calcutta`→**Kolkata**, `trivandrum`→**Thiruvananthapuram**, `madras`→**Chennai**
  (+ identity entries for Pune/Hyderabad/Chennai/Kochi).
- **State/country-aware disambiguation.** Text is split on commas
  (`"Gurugram, Haryana, India"` → city/state/country); when a state and/or
  country is present the candidate rows are narrowed by them first.
- **Unique-active-only auto-map.** Only active Location Master rows are matched,
  and only when **exactly one** row remains. Ambiguous (multiple same-named cities)
  or zero matches **stay unmapped** — the city is never guessed.
- Unmapped → the original text is kept in `current_location_text` (≤150) with a
  row-level warning recommending the admin map/add the city.

## DOB sanity & truncation warnings

- **DOB dropped, age kept.** A future DOB, or one implying an implausible age
  (outside 14–100), is left blank **with a warning**; the imported **age snapshot
  is still kept**. A DOB whose implied age differs from the imported age by **>2
  years** keeps both but warns of the mismatch.
- **Truncation warnings** (row still imports): name >100, current employer >100,
  designation >120, postal address >255.

## Workflow — preview → confirm

The UI **previews then confirms a draft**; a raw-file import is a fallback.

1. **Download sample template.**
2. **Preview / Validate** (`POST /api/candidates/bulk-preview/`) — parse + validate
   + classify every row, **no candidate writes**. Returns per-row `status`
   (`VALID` / `UPDATE` / `DUPLICATE` / `INVALID`), the **Excel row number**, all
   errors + warnings, a **validation summary**, and a non-blocking duplicate-file
   flag. Crucially it persists a reusable **DRAFT `bulk_import_batch`** capturing the
   exact validated dataset and returns its **`batch_id`**.
3. **Import** (`POST /api/candidates/bulk-upload/`, optional `requirement` + `source`):
   - **Preferred:** send the `batch_id` to **confirm the draft** — `confirm_import_batch`
     performs an **atomic DRAFT→PENDING claim** (a concurrent/double confirm cannot
     import twice) and imports the exact rows captured at preview (no re-upload,
     no re-parse). Only the uploader or an admin may confirm a draft.
   - **Fallback:** send a raw `file` (no `batch_id`) → `import_candidates_excel`
     re-parses and imports directly.
   - Either path: **valid rows only** are written; invalid rows never block valid
     ones; each row upserts in its own transaction (partial success). Possible
     duplicates (same mobile, different email) route to the Admin duplicate-review
     queue. `source`/`requirement` are chosen at confirm time.
4. **Download report** — CSV built client-side from the response, or the server-side
   xlsx at `GET /api/import-batches/{id}/report/`.

**Draft lifecycle.** Re-previewing the same file supersedes the prior draft (drafts
don't pile up). Drafts have a TTL of **`BULK_DRAFT_TTL_HOURS` (24h)**; stale drafts
are hard-deleted by the daily maintenance job (`purge_stale_draft_batches`) — safe,
as a draft creates no candidates.

## Row classification (UPDATE vs DUPLICATE) & email guard

Classification runs in memory against a bounded pre-load of the existing candidates
a file's mobiles/emails could clash with (two scoped queries, not one per row); the
DB uniqueness constraints + `upsert_candidate` remain the authoritative write path.

- No mobile match → **VALID** (create) — unless the email already belongs to a
  **different** candidate (email is unique) → **INVALID** (email conflict).
- Same mobile **+ same email** → **UPDATE** the existing candidate.
- Same mobile, **different email** → **DUPLICATE** → Admin review (not imported).

`UPDATE` and `DUPLICATE` rows carry `existing_cv_serial` / `existing_cv_id` for
display in the preview.

## Validation rules & summary

- Required: Candidate Name, Contact No., Email.
- Email format; mobile must resolve to 10 digits.
- **In-file duplicates → INVALID:** a duplicate mobile *or* a duplicate email
  within the same file marks the later row invalid (referencing the earlier row).
- All errors collected per row (never stop at the first).
- **Warnings** (row still imports): unmapped location, non-INR/unparseable/out-of-range
  salary, unparseable experience, DOB dropped / age-DOB mismatch, multiple contact
  numbers, truncated name/employer/designation/address.
- **Summary counters** returned by preview: `total`, `valid`, `update`,
  `duplicate`, `invalid`, `warnings` (rows with ≥1 warning).

## Limits & errors

- **`BULK_MAX_BYTES` (5 MB)** — enforced in the view **before parsing**; oversized
  uploads get a clean 400. Non-`.xlsx` filename → 400.
- **`BULK_MAX_ROWS` (5000)** — enforced **after parsing** (the parser stops one row
  past the cap); over-limit → 400 asking the user to split the file.
- **`BulkParseError` → 400** — a corrupt / empty / password-protected / non-xlsx
  workbook (or a sheet with no detectable header row) surfaces as a clean 400,
  never a 500.

## Import History & Rollback — `/api/import-batches/`

Read-only history + audit (`ImportBatchViewSet`); DRAFT batches are excluded (they
are transient preview state). Recruiters see **their own** uploads; admins see all.

- `GET /api/import-batches/` — list; `GET /api/import-batches/{id}/` — retrieve.
- `GET …/{id}/report/` — download the stored per-row report as an **.xlsx**.
- `POST …/{id}/mark-failed/` — **admin only**; recover a batch stuck in `PENDING`
  (e.g. after a crash) by flipping it to `FAILED`.
- `POST …/{id}/rollback/` — admin **or** the uploader. Only a `COMPLETED` batch can
  be rolled back. **Soft-deletes (`is_active=False`) only the candidates this batch
  CREATED that are still untouched** — global status `NEW_CV` and **not** in any
  requirement pipeline. Candidates the batch merely **UPDATED are never reversed**
  (no pre-import snapshot exists); created-but-worked candidates are kept and
  reported with a reason. Marks the batch `ROLLED_BACK`; rolled-back rows drop out
  of the candidate-database list view.

**Batch statuses:** `DRAFT` → `PENDING` → `COMPLETED` / `FAILED` / `ROLLED_BACK`.

## Robustness

- **Duplicate-file detection** — each upload's bytes are SHA-256 hashed; a match
  against a prior **COMPLETED** batch surfaces a **non-blocking** "already uploaded"
  warning (the import still proceeds).
- **Progress checkpointing** — running counts are flushed every
  **`PROGRESS_FLUSH_EVERY` (50)** rows, so History reflects progress even if the
  process is killed mid-import (the row report + `COMPLETED` are written at the end).
- **Stale-PENDING recovery** — the daily job (`fail_stale_import_batches`) marks any
  batch stuck `PENDING` for more than **30 minutes** as `FAILED` (only ever touches
  still-PENDING rows, so it's idempotent).

## Admin location reconciliation

Link import "kept as text" locations to Location Master after the fact:

- `GET /api/candidates/unmapped-locations/` — distinct `current_location_text`
  values still unmapped (FK NULL), with candidate counts and a **suggested** match
  (alias map + case-insensitive). Never creates a master row.
- `POST /api/candidates/reconcile-location/` (`{text, location_id}`) — set the FK
  and clear the text for **every still-unmapped** candidate with that exact text.
  Only touches rows with a NULL FK, so it never overrides a manually-set location.
  Does **not** create master rows.
- **UI** (`UnmappedLocationsDialog`): recruiters map each unmapped text to an
  existing city. Admins additionally get an inline **Add Location** flow with a
  **drag-to-fill** aside — drag an unmapped text onto the City field of the master
  create dialog; on save the new city is created and the matching unmapped rows are
  auto-reconciled.

## Schema

- **Migration 0024** (additive, nullable, backward compatible): `candidate_master`
  gains `date_of_birth date`, `age_at_import smallint`, `postal_address varchar(255)`,
  `current_location_text varchar(150)`. No changes to existing columns; no backfill.
- **Migration 0025** (additive): new table **`bulk_import_batch`** (metadata, counts,
  `status`, `file_hash`, `header_row`, per-row `row_report` jsonb, timestamps) plus a
  nullable FK **`candidate_master.import_batch_id`** → the batch that CREATED the
  candidate (NULL for manual / bulk-UPDATED candidates; the rollback anchor).
