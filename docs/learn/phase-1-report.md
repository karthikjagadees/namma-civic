# Phase 1 report: incident data model

## Goal

Add a durable model for real-world incidents, preserved citizen reports, and work orders. Keep the original complaint evidence intact while making important link and work-order rules testable in the database.

## Approved decisions

- A report matching a resolved incident starts a new incident by default.
- A report that could bridge two incidents goes to officer review.
- If an officer rejects a link, the report is reassigned and the previous link remains in history.
- Backfilled links use a distinct `backfill` decision source so they are not mislabeled as automatic or officer decisions.

## What changed

- Added SQLAlchemy `Incident`, `ReportLink`, and `WorkOrder` models and their relationships.
- Added an initial-link helper for API-created and demo-seeded complaints, plus an audited link-reassignment helper.
- Added two Alembic revisions: a baseline for the existing schema, then incident/work-order tables and a backfill.
- Changed database initialization to apply migrations. Complete legacy `create_all()` schemas are stamped at the baseline before upgrading; incomplete unversioned schemas are rejected.
- Added tests for schema constraints, model/migration parity, legacy upgrade/backfill, preservation of report and media fields, startup adoption, and initial links.
- Added `docs/learn/01-data-model.md` with an ER diagram, worked five-report example, invariants, and policies.

## How the model works

Each Complaint remains a separate record containing its reporter, text, location, channel, and media. A ReportLink connects it to an Incident. Link corrections create a replacement row that points to the superseded row, keeping the old decision and its evidence.

A partial unique index limits each complaint to one active link. Another partial unique index allows at most one active WorkOrder per incident; completed and cancelled work orders do not count as active. The incident reporter set is derived from active links to complaints instead of maintaining a separate reporter list.

Every existing complaint receives its own incident during backfill. New API and demo seed reports also receive an initial incident and link. This phase does not yet run duplicate detection to combine reports into a shared incident.

## Test-first and final evidence

The incident tests were added before the models and migration. The first focused run reported **4 failures**, confirming that the expected model classes and Alembic revisions did not yet exist.

Focused command and final result:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests/test_incidents.py -q
```

**8 passed, 2 warnings.**

Full backend suite command and final result:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests -q
```

**69 passed, 36 warnings.** No tests were deleted or weakened. The tests ran on SQLite; PostgreSQL execution was not verified in this phase.

## Phase 1 status and remaining work

The incident data model, backfill, and test coverage are in place. The duplicate detector and LangGraph action node are not yet wired to the model, so likely duplicates can still cause independent work-order dispatches. Persisted WorkOrder creation by incident, duplicate matching, concurrent incident creation, officer review UI, and incident-wide notifications remain for later phases.
