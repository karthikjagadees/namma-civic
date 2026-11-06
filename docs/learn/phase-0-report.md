# Phase 0 report: project orientation and test baseline

## Goal

Understand the existing Namma Civic architecture, verify the project review findings, and make the backend test suite reliable without changing product behavior.

## What changed

- `backend/tests/conftest.py` initializes the test database before tests and forces the mock AI provider. The later Phase 1 update also moved test data and uploads to a temporary directory and isolated tests from `.env` settings.
- `docs/learn/00-system-map.md` documents the complaint lifecycle, the six graph nodes, failure behavior, and real versus simulated integrations.
- `docs/learn/requirements-traceability.md` maps the problem statement and duplicate constraint to code or a gap.

## How the existing system works

The API saves a complaint, its media, and an initial timeline entry. Orchestration is a separate API call. It runs six LangGraph nodes: intake, validation, deduplication, routing, approval, and action. The graph uses an in-memory `MemorySaver`; it does not survive a server restart.

The duplicate node scans active complaints, compares distance within a fixed 100-meter radius and token Jaccard similarity, then returns the first match. It does not create a stored incident link. The action node can still dispatch work for each complaint.

## Verified findings

- Duplicate flags do not prevent separate work orders; no Incident or ReportLink existed at the Phase 0 baseline.
- Deduplication ignores photos and report channel, scans the query results in Python, takes the first acceptable match, and treats a database error as no duplicate.
- Complaint sources include web, mobile, voice, and WhatsApp, but deduplication and routing do not use source. Intake analyzes only the first media URL.
- The README overstates the graph as ten agents and lists directories that are absent from this checkout. Six graph nodes are implemented. Alembic configuration existed without revision files; startup used `Base.metadata.create_all()`.
- The action node used a hardcoded SMS destination and could report dispatch after a database write failed. SMS was simulated by the local handler.
- Analytics hotspot clustering uses a separate nested loop; it is not the duplicate detector.
- The reported missing-table test failures were caused by test setup. HTTPX `ASGITransport` did not start FastAPI lifespan, and the original test fixture did not initialize tables.

## Test evidence

Before the Phase 0 fixture fix, the isolated backend run collected 61 tests and reported **17 passed, 44 failed**. The failures included missing database tables.

After the fix, from the backend directory, the command was:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests -q
```

The result was **61 passed, 36 warnings**. No live LLM calls were made; the tests used the mock provider. The warnings were Pydantic protected-name and JWT datetime deprecations.

## Phase 0 status

The test baseline and orientation documents were completed. The core duplicate constraint remained open: reports were not linked to a common incident, and action could still dispatch separate work orders.
