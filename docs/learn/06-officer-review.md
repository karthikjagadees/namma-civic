# Phase 6 — Officer review and feedback loop

This phase gives municipal staff a queue for uncertain duplicate matches. Each decision changes only the report-to-incident association history; the original citizen report and media remain intact.

## Review lifecycle

```mermaid
sequenceDiagram
    participant Graph as Agent action node
    participant DB
    participant Officer as Officer review UI
    participant Service as Review service
    participant Calibrator as Threshold script

    Graph->>DB: Save grey-zone case, candidate scores and signal evidence
    Graph->>DB: Keep report in verified state; do not dispatch new work order
    Officer->>Service: Load officer-only review queue
    Service->>DB: Read report, candidate incidents, photos, coordinates and active links
    Service-->>Officer: Side-by-side evidence and explainable signals
    Officer->>Service: Confirm, reject, merge, or split with a note
    Service->>DB: Version report links; save officer label and incident audit event
    Service->>DB: Consolidate or queue work orders as needed
    Calibrator->>DB: Read latest officer labels per report/candidate/officer
    Calibrator-->>Officer: Print current and proposed thresholds; apply nothing
```

## What the officer sees and can do

The officer-only `GET /api/officer/duplicate-reviews` endpoint returns each pending report next to its candidate incident. The UI includes the original text and channel, photo references, each side's coordinates/address with OpenStreetMap map previews, candidate status, distance, fused score, and per-signal values. It omits reporter contact details.

The `POST /api/officer/duplicate-reviews/{review_id}/decision` endpoint supports:

- **Confirm link:** creates a new officer-authored `ReportLink` version. If the candidate already resolved, it creates a new recurrence incident instead of reopening the resolved record.
- **Reject match:** records a negative label and keeps the report on its independent incident. It ensures the incident has a queued/active work order so review does not strand the report.
- **Merge incidents:** moves every active report link from the reviewed report's provisional incident to the chosen incident, retains prior link rows, and consolidates active work orders. The source incident is retained and closed with a merge timeline entry.
- **Split report:** creates a new incident for this report and versions its link to that incident. A queued order is added. This is the safe meaning of “unlink” while preserving the system invariant that each report has one active incident association.

Every action saves an immutable `DuplicateReviewDecision` with the binary duplicate label, score, signal snapshot, officer, action, and note. It also appends incident timeline audit events. The original complaint text, media, channel, location, and reporter are not overwritten.

## Feedback metrics

`GET /api/analytics/duplicate-operations` is officer-only. It calculates:

- `duplicates_linked`: active report links beyond the first on each incident.
- `work_orders_avoided`: a data-based estimate for multi-report incidents with an active order: report count beyond active order count, capped at the duplicate-link count. It is a proxy from current records, not a measured counterfactual of how many orders would have been created without deduplication.
- `review_queue_volume`: persisted cases whose status is pending.
- `officer_agreement_rate`: for report/candidate pairs reviewed by at least two distinct officers, the fraction of votes agreeing with that pair's majority label. The latest label per officer is used. It is `null` when no pair has multiple independent officer labels.

These metrics are derived from persisted links, work orders, cases, and decisions, rather than sample or synthetic counters.

## Threshold review script

From `backend/`, after the database has been migrated, run:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\recalibrate_duplicate_thresholds.py
```

The script uses the latest persisted officer label for each report/candidate/officer tuple. It prints current and proposed auto-link/review thresholds and labeled-pair precision/recall/F1. It does **not** change runtime thresholds, files, or database rows. Small or biased officer samples can produce unstable recommendations; review the sample count and cases before proposing any threshold change.

## Limits and decisions

- Case storage is one review case per complaint. The candidate list is the resolver snapshot at review time; the queue joins current incident/report/photo data for display.
- Work-order consolidation is local database state. If a real municipal dispatch provider has already accepted a work order, this phase does not send it a cancellation/merge command.
- The map preview uses OpenStreetMap over the network; the comparison API and tests run offline, but an offline browser cannot load map tiles.
- The threshold script reports recommendations only. Applying them remains a later, reviewed configuration decision.
- Agreement requires at least two distinct officers on the same report/candidate pair; the metric is null before that evidence exists.

## See it locally

From `backend/`, run the offline review tests:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_officer_duplicate_review.py -q --tb=short
```

The suite uses the mock AI/MCP configuration and local SQLite; it makes no live provider calls.
