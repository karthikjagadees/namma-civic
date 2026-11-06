# Phase 7: End-to-end verification, privacy, and failure handling

## What this phase verifies

The scenario test uses five **synthetic** reports from four channels, different descriptions, and similar synthetic photo hashes. Reports arrive one at a time, as they would in normal intake. The scenario verifies one incident, one work order, five preserved complaint rows and media records, and a delivered notification record for each reporter. The test simulates municipal notification and work-order tools locally; it does not send real SMS, email, or dispatch requests.

The synthetic hard-negative check puts two differently photographed pothole reports about 29 metres apart. Strongly conflicting photo evidence sends that case to officer review, preventing an automatic merge. This does not claim that pHash can identify every different pothole; it provides a conservative conflict signal.

## Walkthrough

1. The test database is created in a temporary directory, migrated to the current Alembic head, and seeded with the project's deterministic development records. The test configuration uses the mock AI provider and mock MCP mode.
2. Each synthetic citizen submits an immutable complaint with its own channel and media evidence. A provisional incident is created for that report.
3. Intake and the graph's other nodes run. If the incident's accumulated report count raises its priority to a human-review threshold, the test simulates officer approval before the graph resumes.
4. The action node takes the DB serialization lock and scores candidates again. It links a matching report, preserves the original complaint and evidence, folds an empty provisional incident into the canonical incident while retaining its retired ID in link evidence, and reuses the incident's one work order.
5. The deterministic test tool records delivery results. The test checks that each of the five citizen IDs appears as a delivered recipient.
6. Separate API tests check report ownership, safe public incident-tracker fields, idempotent webhook replay, malformed image rejection, AI-provider fallback, and the existing action persistence-failure path.

## Access and failure behavior

- Citizens must authenticate to list or retrieve complaint records. Their list is scoped to their own reports. A citizen requesting another person's report receives `404`, which avoids confirming that a private report ID exists. Officers and admins can inspect other reports.
- Agent orchestration/state, stored AI analysis, reanalysis, complaint AI triage, and resolution verification enforce ownership or staff authorization at their API boundary. Resolution verification is officer/admin only and uses the authenticated officer ID.
- The public incident tracker exposes operational status and aggregate report count, but not reporter IDs, contact details, report descriptions, or reporter names.
- Submitted complaint title, description, and category cannot be overwritten through the update endpoint. Officers can still change operational fields and append timeline notes.
- A failed AI provider produces an explicit fallback result and requires officer review. It does not invent a classification or continue as if AI succeeded.
- A failure while persisting the action returns a failed action result and does not claim dispatch. The database-failure test uses a deterministic failing session; it does not simulate a real network partition or crash recovery.
- Image uploads still check allowed MIME types and size. Image bytes are now opened and verified; invalid content is deleted and rejected. This verification is specifically for image content; it does not establish safety scanning for every supported audio or document format.
- Complaint creation accepts an optional `Idempotency-Key`. The database enforces uniqueness per citizen, and a repeated key returns the existing report. Callers that omit the key do not get replay protection.

## Evidence from this run

All data in the five-report demo is **synthetic**. From `backend/`, using the existing Phase 0 virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=short --disable-warnings
```

Actual output: `134 passed, 55 warnings in 23.42s`.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\run_phase7_demo.py
```

Actual scenario output:

```text
{'dataset_kind': 'synthetic', 'reports_preserved': 5, 'channels': 4, 'incidents': 1, 'work_orders': 1, 'reporters_notified': 5}
1 passed, 6 deselected in 3.75s
```

The demo wrapper uses pytest's temporary seeded SQLite database. The tests replace the MCP tool call with a deterministic in-process fake. The counts above describe only this synthetic run, not production traffic or quality.

The Phase 7-specific tests are in `backend/tests/test_phase7_verification.py`. The existing action database-failure test is in `backend/tests/test_pipeline_agents.py`; migration adoption is covered in `backend/tests/test_incidents.py`.

## Remaining risks and limits

- The graph checkpointer is still in-memory. A process restart loses paused graph state; committed complaint, incident, link, work-order, and timeline rows remain in SQL. Durable graph-state recovery has not been implemented.
- The global DB write lock is a correctness-oriented prototype. Production database lock contention and parallel throughput still need deployment verification.
- Photo URLs in the synthetic scenario do not point to real photographs. Similarity behavior here exercises stored pHash evidence deterministically, not a computer-vision benchmark.
- The new idempotency column is optional for backwards compatibility. External channel adapters must pass a stable key to benefit from deduplication of webhook retries.
- No security audit or production penetration test was run in this phase.

## Try it

From `backend/` in PowerShell:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\run_phase7_demo.py
```

The command reports a **synthetic** scenario and runs offline with mock AI and mocked delivery/dispatch tools.
