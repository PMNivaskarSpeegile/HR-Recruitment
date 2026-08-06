# Workflow, Sequence & State Diagrams

## Recruitment workflow (end to end)
```mermaid
flowchart TD
  A["HM creates requirement (UC1)"] --> B["HM assigns recruiter (UC1)"]
  B --> C["Recruiter adds candidates (UC2) — tagged to the requirement's Review Pool"]
  C --> D["Review Pool: Verify & Update → decide (UC3)"]
  D -->|Shortlist| E["Enters pipeline (jd_cv_mapping)"]
  D -->|Not Suitable / Talent Pool / Fake / Blacklist| Z["Review resolved (no pipeline entry)"]
  E --> F["Send JD email to shortlisted (UC4)"]
  F --> G["Schedule screening / drop / no-response (UC5)"]
  G --> H["Screening outcome → OK to Proceed / Rejected (UC5)"]
  H --> I["Release Offer → Accepted → Awaiting Joining → Joined (UC5)"]
  classDef done fill:#d6f5d6,stroke:#2e7d32;
  class A,B,C,D,E,F,G,H,I,Z done
```

Two membership concepts are kept **separate** throughout:
- **Review Pool** (`candidate_requirement_review`, status `ACTIVE`) — the candidate is *under review* for a requirement. Membership is the **explicit tag**, never skill matching.
- **Pipeline** (`jd_cv_mapping`) — the candidate has *entered* the pipeline (only ever via **Shortlist**).

## UC1 — Create & assign requirement
```mermaid
sequenceDiagram
  actor HM as Hiring Manager
  participant V as RequirementViewSet
  participant Svc as requirements.services
  participant Pos as requirements.positions
  participant DB
  HM->>V: POST /api/requirements/
  V->>V: validate (exp range, client↔mgr)
  V->>Svc: create_requirement(data, user)
  Svc->>DB: next REQ/JD number (txn + retry)
  Svc->>DB: INSERT requirement (status=New, hiring_mgr=HM)
  Svc->>Pos: create_positions_for_requirement (one Open seat per opening)
  Svc-->>HM: 201 {req_tracker_no, jd_serial_number, ...}
  HM->>V: POST /api/requirements/{id}/assign/ {recruiter}
  V->>Svc: assign_requirement(req, recruiter, user)
  Svc->>DB: recruiter set, status=Assigned, assigned_date
  Svc-->>HM: 200 {status: Assigned}
```

## UC2 — Candidate create / duplicate logic (+ Review Pool tagging)
`upsert_candidate` is the single create/update path (manual form, bulk import, Verify & Update). Passing a `requirement` also **tags the candidate into that requirement's Review Pool** as a side effect (never a `jd_cv_mapping`).
```mermaid
sequenceDiagram
  actor R as Recruiter
  participant V as CandidateViewSet
  participant Svc as candidates.services
  participant DB
  R->>V: POST /api/candidates/ {mobile,email,... , requirement?}
  V->>Svc: upsert_candidate()
  Svc->>DB: detect_duplicate(mobile, email)
  alt no mobile match
    Svc->>DB: INSERT (CV serial, New_CV) + tag skills
    Svc->>DB: log_activity(candidate_added)
    Svc->>Svc: if requirement → tag_candidate_for_review (Review Pool ACTIVE)
    Svc-->>R: 201 CREATED
  else mobile + same email
    Svc->>DB: UPDATE existing (+ tag skills)
    Svc->>Svc: if requirement → tag_candidate_for_review
    Svc-->>R: 200 UPDATED
  else mobile match, email differs
    Svc-->>R: 409 POSSIBLE_DUPLICATE (no write, Admin review queued)
  end
```

## UC3 — Review Pool + the two decision paths
The Review Pool for a requirement = candidates **explicitly tagged** `ACTIVE` in `candidate_requirement_review` (minus those already mapped / Fake / Blacklisted). Skill overlap is used **only to rank** within that set (`matched_skills`, best first), never for membership.

There are **two live decision endpoints**:
```mermaid
sequenceDiagram
  actor R as Recruiter
  participant NV as NewCvListView
  participant RV as ReviewView (POST /api/pipeline/review/)
  participant VP as CandidateViewSet (POST /api/candidates/{id}/verify-profile/)
  participant P as pipeline.services
  participant C as candidates.services
  participant DB
  R->>NV: GET /api/pipeline/new-cvs/?requirement=
  NV->>DB: Review-Pool tagged (ACTIVE) + skill-ranked, not-yet-mapped
  NV-->>R: ranked candidate list

  Note over RV: Path 1 — quick 2-way review (Shortlist / Not Suitable ONLY)
  R->>RV: POST /api/pipeline/review/ {decision}
  alt SHORTLISTED
    RV->>P: review_candidate — get_or_create jd_cv_mapping at Shortlisted, candidate to Talent Pool
  else NOT_SUITABLE
    RV->>P: review_candidate — mapping at Not_Suitable (closed), candidate stays Talent Pool
  end
  RV-->>R: 200 {decision, candidate_status, mapping}

  Note over VP: Path 2 — Verify & Update + the 5-way decision
  R->>VP: POST /api/candidates/{id}/verify-profile/ {profile, decision, requirement?}
  VP->>C: verify_and_update_candidate (field audit + verify stamp)
  VP->>C: apply_candidate_decision(decision)
  alt Shortlist
    C->>P: enter_pipeline — jd_cv_mapping at Shortlisted + resolve review (SHORTLISTED), candidate to Talent Pool
  else Not Suitable
    C->>DB: resolve review (NOT_SUITABLE) ONLY — NO mapping, NO global status change
  else Talent Pool
    C->>DB: candidate to Talent Pool + resolve review (TALENT_POOL), no mapping
  else Fake / Blacklist
    C->>DB: candidate to Fake/Blacklisted + resolve ALL active reviews, no mapping
  end
  VP-->>R: 200 {candidate, decision}
```
Key rule: **Not Suitable does NOT create a `jd_cv_mapping` and does NOT change the candidate's global status** — it only resolves the pre-pipeline review association.

## Review Pool tagging / untagging
```mermaid
sequenceDiagram
  actor R as Recruiter
  participant V as CandidateViewSet
  participant Svc as candidates.services
  participant DB
  R->>V: POST /api/candidates/{id}/tag-requirements {requirement_ids[]}
  V->>Svc: tag_candidate_for_review(candidate, requirement)
  Svc->>Svc: guard — candidate usable (not Fake/Blacklisted) & requirement WORKABLE, not expired/ended
  Svc->>DB: get_or_create ACTIVE review (idempotent, reactivate if RESOLVED)
  Svc-->>R: review row (Review Pool membership)
  R->>V: POST /api/candidates/{id}/untag-requirement {requirement}
  V->>Svc: untag_candidate_review → resolve review as UNTAGGED
```

## Requirement lifecycle (state)
Auto rollup (`recompute_requirement`) derives **Assigned / Open / Partial Filled / Close Filled** from the seats; manual HM actions drive **Hold / Cancelled / Close Lost**. **Expired is NOT a stored state** — it is a derived, read-only overlay (`requirement_is_expired`: Target Fill Date passed while non-terminal) that clears the moment the date is extended.
```mermaid
stateDiagram-v2
  [*] --> New: create (+ Open seats)
  New --> Assigned: assign recruiter
  New --> Open: first candidate linked
  Assigned --> Open: first candidate linked
  Open --> Partial_Filled: seat filled (rollup)
  Partial_Filled --> Close_Filled: all seats filled (rollup)
  Open --> Close_Filled: single/last seat filled (rollup)

  Assigned --> Hold: HM hold
  Open --> Hold: HM hold
  Partial_Filled --> Hold: HM hold
  Hold --> Open: HM resume

  Assigned --> Cancelled: HM cancel (reason)
  Open --> Cancelled: HM cancel (reason)
  Partial_Filled --> Cancelled: HM cancel (reason)
  Hold --> Cancelled: HM cancel (reason)
  Cancelled --> Open: HM reopen

  Assigned --> Close_Lost: HM close lost (reason)
  Open --> Close_Lost: HM close lost (reason)
  Partial_Filled --> Close_Lost: HM close lost (reason)
  Hold --> Close_Lost: HM close lost (reason)

  Close_Filled --> [*]
  Close_Lost --> [*]
  note right of Partial_Filled
    Expired overlay (derived, not stored).
    On an EXPIRED Partial Filled req the HM may
    End Recruitment: status STAYS Partial Filled,
    remaining seats withdrawn, applications freed.
  end note
```
Hold/Cancel/Close-Lost are allowed from any active state (Assigned / Open / Partial Filled) and from Hold. Cancelled is reopenable (→ Open); Close Lost is terminal.

## Requirement Hold / Cancel / Reopen + closure cascade
```mermaid
sequenceDiagram
  actor HM as Hiring Manager
  participant V as RequirementViewSet (POST /api/requirements/{id}/set-status/)
  participant Svc as requirements.services
  participant Pos as requirements.positions
  participant P as pipeline.services
  participant DB
  HM->>V: set-status {to_status, reason}
  V->>Svc: change_requirement_status()
  Svc->>Svc: guard MANUAL_REQ_TRANSITIONS + mandatory reason (Hold/Cancel/Close-Lost)
  Svc->>DB: set req_status + status_change_history (MANUAL)
  alt Hold
    Svc->>Pos: cascade_on_hold — Open seats → Inactive (AUTO_REQ_HOLD)
  else Resume (Hold → Open)
    Svc->>Pos: cascade_on_resume — only Hold-inactivated seats → Open
  else Reopen (Cancelled → Open)
    Svc->>Pos: cascade_on_reopen — all system-inactivated seats → Open
  else Cancelled / Close Lost
    Svc->>Pos: cascade_on_cancel — Open seats → Inactive (AUTO_REQ_CANCEL)
  end
  opt Close Lost (irreversible)
    Svc->>P: close_remaining_applications(REQ_CLOSE_LOST) → candidates freed to Talent Pool
    Svc->>DB: resolve_reviews_for_requirement (Review Pool emptied)
  end
  Note over Svc,DB: Cancelled is reopenable → its pipeline + Review Pool are PRESERVED
  Svc-->>HM: 200 {status}
```

## Requirement End Recruitment (expired, partially filled)
```mermaid
sequenceDiagram
  actor HM as Hiring Manager
  participant V as RequirementViewSet (POST /api/requirements/{id}/end-recruitment/)
  participant Svc as requirements.services
  participant Pos as requirements.positions
  participant P as pipeline.services
  participant DB
  HM->>V: end-recruitment {reason}
  V->>Svc: end_recruitment()
  Svc->>Svc: precondition — status == Partial Filled AND expired (else 400), idempotent if already ended
  Svc->>DB: persist recruitment_ended / _on / _by  (FIRST — freezes the rollup)
  Svc->>Pos: cascade_on_end_recruitment — remaining Open seats → Inactive (AUTO_END_RECRUITMENT)
  Svc->>P: close_remaining_applications(REQ_POSITIONS_WITHDRAWN) → Talent Pool
  Svc->>DB: resolve_reviews_for_requirement (Review Pool emptied)
  Note over Svc,DB: status STAYS Partial Filled (+ Expired overlay) — withdrawn seats never roll it to Close Filled
  Svc-->>HM: 200 {closed, requirement}
```

## Candidate global status (state)
A per-requirement decision never changes the global status; only the automation below does. **Not Suitable causes NO status change.** Fake/Blacklisted are hard and never overridden.
```mermaid
stateDiagram-v2
  [*] --> New_CV: created (UC2)
  New_CV --> Saved: Shortlist / Talent Pool / non-hired close (opt-in)
  Saved --> Saved: re-shortlisted / re-tagged
  New_CV --> Joined: application Joined
  Saved --> Joined: application Joined
  New_CV --> Reject_Hold: 2nd active rejection (6-month cool-off)
  Saved --> Reject_Hold: 2nd active rejection (6-month cool-off)
  Reject_Hold --> Saved: cool-off elapsed (daily job, counter reset)
  Joined --> Saved: 2 years after joining (daily job)
  New_CV --> Fake: decision (Verify & Update / pipeline)
  Saved --> Fake: decision
  New_CV --> Blacklisted: decision
  Saved --> Blacklisted: decision
  Fake --> [*]
  Blacklisted --> [*]
  note right of New_CV
    "Saved" is displayed as "Talent Pool".
    Not Suitable → NO global change.
    Possible-duplicate detection is a SEPARATE
    review process (candidate_duplicate_review) —
    it never sets a global candidate status.
    A single rejection only moves to Talent Pool
    if the recruiter opts in.
  end note
```

## Per-requirement pipeline (jd_cv_mapping) — stage × outcome engine
`application_stage` holds the STAGE; `latest_outcome` holds the last OUTCOME; `is_closed` marks a terminal close. Advancing ACTIONS (solid) are side-effecting buttons; closing OUTCOMES (dashed) end the application and drive the candidate's global status via `apply_application_outcome`.
```mermaid
stateDiagram-v2
  [*] --> Shortlisted: Shortlist (enter_pipeline)
  [*] --> Not_Suitable: review_candidate Not Suitable (closed)
  Shortlisted --> JD_Email_Sent: Send JD (action, UC4)
  JD_Email_Sent --> Screening_Scheduled: Schedule Screening (action, future dt)
  JD_Email_Sent --> Dropped: Drop (close)
  Screening_Scheduled --> OK_to_Proceed: Passed
  Screening_Scheduled --> Rejected: Rejected (close)
  Screening_Scheduled --> No_Response: No Response (close)
  Screening_Scheduled --> Dropped: Dropped (close)
  Screening_Scheduled --> Fake: Fake (close)
  Screening_Scheduled --> Blacklisted: Blacklisted (close)
  OK_to_Proceed --> Offered: Release Offer (action)
  OK_to_Proceed --> Rejected: Rejected (close)
  OK_to_Proceed --> Dropped: Dropped (close)
  OK_to_Proceed --> Fake: Fake (close)
  Offered --> Awaiting_Joining: Offer Accepted
  Offered --> Offer_Declined: Offer Declined (close)
  Awaiting_Joining --> Joined: Joined (consumes one Open seat)
  Awaiting_Joining --> Withdrawn: Withdrawn (close)
  Joined --> [*]
```
Joining consumes one Open seat (`_consume_open_position`, over-fill safe with `select_for_update(skip_locked)`); filling the last seat triggers the requirement `Close Filled` rollup, which auto-closes the remaining applications back to the Talent Pool.

## Screening schedule / reschedule / complete
Screenings are separate rounds on an application; every incoming datetime is normalized with `to_local_naive` and must be in the future.
```mermaid
sequenceDiagram
  actor R as Recruiter
  participant V as ScreeningListCreateView
  participant Svc as pipeline.screening
  participant DB
  R->>V: POST /api/pipeline/screenings/ {mapping, mode, scheduled_at}
  V->>V: scope to recruiter's requirement (workable)
  V->>Svc: schedule_screening (to_local_naive, must be future)
  Svc->>DB: INSERT screening (SCHEDULED) + advance mapping → Screening_Scheduled
  Svc-->>R: 201 screening
  R->>V: POST /api/pipeline/screenings/{id}/reschedule/ {scheduled_at}
  V->>Svc: reschedule_screening_round (future dt, stage unchanged)
  Svc-->>R: 200 screening
  R->>V: POST /api/pipeline/screenings/{id}/complete/ {outcome, notes?}
  V->>Svc: complete_screening (Passed/Failed/No-Show/…) → records mapping outcome
  Svc-->>R: 200 screening
```

## Bulk import — preview → confirm → rollback
```mermaid
sequenceDiagram
  actor R as Recruiter
  participant V as CandidateViewSet
  participant Svc as candidates.services
  participant DB
  R->>V: POST /api/candidates/bulk-preview/ (file .xlsx)
  V->>Svc: preview_candidates_excel()
  Svc->>Svc: parse (auto-detect header) + validate + classify (VALID/UPDATE/DUPLICATE/INVALID)
  Svc->>DB: create DRAFT BulkImportBatch (validated rows stored, supersedes prior draft)
  Svc-->>R: {summary, per-row status/errors, batch_id, duplicate_file?}
  R->>V: POST /api/candidates/bulk-upload/ {batch_id, source?, requirement?}
  V->>Svc: confirm_import_batch()
  Svc->>DB: atomic DRAFT→PENDING claim (double-confirm safe)
  loop each stored row
    Svc->>Svc: upsert_candidate() — DB uniqueness authoritative
    alt CREATED
      Svc->>DB: INSERT + stamp import_batch (rollback anchor), if requirement → Review Pool tag
    else UPDATED
      Svc->>DB: UPDATE existing
    else POSSIBLE_DUPLICATE
      Svc->>DB: record to Admin duplicate-review queue
    end
  end
  Svc->>DB: batch → COMPLETED (+ row_report, counts)
  Svc-->>R: import report
  R->>V: POST /api/import-batches/{id}/rollback/
  V->>Svc: rollback_import_batch()
  Svc->>DB: soft-delete ONLY still-New_CV, un-pipelined candidates this batch CREATED
  Note over Svc,DB: UPDATED rows are never reversed — worked/mapped rows are kept
  Svc->>DB: batch → ROLLED_BACK
  Svc-->>R: {removed, kept, updated_not_reversed}
```
Recovery: a PENDING batch whose process died is swept to FAILED (`fail_stale_import_batches`), and DRAFTs past their TTL are purged — both in the daily maintenance job.
