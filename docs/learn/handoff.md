# Namma Civic phase handoff

Update this file at the end of each completed phase so the next work starts from verified project state.

## Follow-up: resolve the two visible streetlight reports as one incident

### Verified cause and change

- In the local demo database, reports `0b51825f…` and `79d38b85…` were about 11.9 m apart, had the same category and identical stored pHash, but had separate provisional incidents.
- Triage paused because a weaker nearby resolved streetlight candidate made the generic active-versus-resolved ambiguity rule send the report to officer review, despite one unique near-exact photo match to an active incident.
- The resolver now auto-links only when there is exactly one active candidate with the same category, pHash similarity at least `0.95`, distance no more than 20 m, and fused score above the calibrated auto-link threshold. If more than one candidate meets that strong evidence rule, it still requests officer review.
- Re-triaged the second report with the local mock provider. The database then showed one active incident for the pair, two active report links, one work order, and the officer queue returned one card with `reporter_count=2`. Both original complaint rows and their original evidence remain stored. The incident priority is high.

### Verification

- Regression tests were added first. Before the matcher change, the test for the unique exact-photo active match failed with officer review; after the change, it auto-links. A companion test confirms that equally strong active and resolved photo matches still go to officer review.
- Focused regression command: four selected duplicate-detection tests returned `4 passed in 2.37s`.
- Related backend suite command `pytest tests\test_duplicate_detection.py tests\test_media_phash.py tests\test_pipeline_agents.py tests\test_officer_admin.py tests\test_phase7_verification.py -q --tb=short --disable-warnings` returned `44 passed, 16 warnings in 8.58s`.
- The local re-triage used `AI_MODE=mock`, `AI_PROVIDER=mock`, and `MCP_MODE=mock`; it made no live LLM/API requests.

### Limits

- The 20 m / pHash exception is a conservative deterministic rule for this specific ambiguity pattern, not a general guarantee that identical-looking photos identify the same physical defect. If multiple candidates share the strong photo/location evidence, human review remains required.
- The running UI/backend must be restarted or reloaded to pick up Python changes; refresh the officer page after the backend is running the updated code.

## Follow-up: exact-photo report after resolution uses recurrence policy

### Verified cause and change

- The next new-account report (`826769d3…`) had the same stored pHash (`8a1b85a5f0d8f45e`) and same streetlight category as the earlier reports. Their shared incident (`57cb0c26…`) had since been marked resolved.
- The user confirmed the earlier policy: keep a new recurrence after resolution. The previous matcher sent this report to review because it saw weaker nearby active candidates as well as the exact-photo resolved candidate.
- The resolver now gives a unique near-exact photo match to a resolved incident precedence over weaker nearby candidates, but still creates a separate recurrence incident referencing the resolved incident. Equally strong photo matches to multiple candidates still go to review.
- Re-triaged the saved report with the local mock provider. It was dispatched to a new recurrence incident (`7487d0c7…`) referencing `57cb0c26…`; the recurrence has one work order and one officer card with `reporter_count=1`. It is intentionally not counted among the citizens attached to the resolved incident.

### Verification

- A regression test was added first and failed before the change (`officer_review` instead of `new_incident`). The focused decision/safety tests returned `5 passed in 1.55s` after the change.
- Related backend suites returned `45 passed, 16 warnings in 20.36s`.
- Re-triage used `AI_MODE=mock`, `AI_PROVIDER=mock`, and `MCP_MODE=mock`; no live API request was made.

### Limits

- A recurrence after resolution intentionally starts a separate incident/work order under the selected policy. To count this reporter with the earlier group, the incident must be reopened instead; that is not the current policy.

## Follow-up: identical-location and photo duplicate aggregation

### Verified behavior

- Added a three-citizen **synthetic** graph scenario with different report text/channels, identical photo hashes, and the same GPS coordinates.
- The existing candidate scorer links the reports to one incident; action reuses one work order; the officer queue emits one incident card with three distinct reporters.
- The report-count priority node raises the synthetic streetlight incident from its high base priority to critical at three independent reporters. The incident SLA calculation returns 12 hours for that critical priority.

### Verification

- The new end-to-end test was written first. Its initial run exposed an incorrect test expectation: mock streetlight evidence already sets a high base priority, so the third-report boost correctly produces critical, not high. The test was corrected to assert the evidence-based result.
- `pytest tests\test_duplicate_detection.py tests\test_media_phash.py tests\test_pipeline_agents.py tests\test_officer_admin.py tests\test_phase7_verification.py -q --tb=short --disable-warnings` returned `42 passed, 16 warnings in 8.94s`.

### Limits

- This is a deterministic synthetic regression, not a benchmark of real image/location accuracy. Real reports with missing coordinates are intentionally sent to officer review.

## Follow-up: opt-in Groq provider

### Delivered

- Confirmed the configured `openai/gpt-oss-120b` model is listed in Groq's supported models.
- Updated `run.ps1` to accept `NAMMA_CIVIC_AI_MODE=groq|openai|gemini`; default remains `mock`. Live mode loads the project `.env` into the backend process and refuses to reuse an existing backend that might still be running in a different mode.
- Updated `docs/learn/08-local-run-and-ui.md` with the opt-in PowerShell commands and provider limitations.

### Verification

- The approved Groq smoke test sent exactly three synthetic text reports and completed three live text requests. Groq returned categories `pothole`, `street_light`, and `garbage`, with severities 8, 5, and 6 respectively. No complaint from a real citizen was sent; no key was printed.
- PowerShell parser accepted `run.ps1` after the launcher change.
- Two setup attempts stopped before provider initialization and made zero API calls (module path, then an invalid inherited `DEBUG` environment value); the corrected run succeeded.

### Boundaries

- The normal launcher remains mock unless the user explicitly opts in with `NAMMA_CIVIC_AI_MODE=groq`.
- The Groq image adapter currently supplies fixed synthetic image findings; this smoke test validates text triage only, not live vision or duplicate-detection accuracy.

## Follow-up: incident queue grouping and reporter escalation

### Verified cause

- The officer API returned one queue item per complaint, and the page labeled those rows as incidents. So even correctly linked reports appeared multiple times.
- Reports submitted before browser orchestration was wired can remain pending; the citizen detail page had a retry, but officers had no triage action to process those saved reports.
- The previous priority rule required four reporters for its first increase, which did not match the expected urgency bump at three independent reporters.

### Delivered

- The officer API now returns one card per linked incident, plus the active report count and distinct citizen count. The complaint and media rows remain unchanged.
- The officer page shows “Reported by N citizens” and provides **Run triage** for pending reports, reusing the saved report ID.
- Three independent reporters now increase priority one level; each two further reporters can raise it another level, up to critical.
- Updated `docs/learn/04-agent-pipeline.md` with the incident queue and priority rules.

### Verification

- The queue grouping and priority tests were run red first, then passed after implementation.
- Relevant targeted checks: `3 passed` across queue grouping, unrouted queue visibility, and priority escalation.
- `npm run build` completed with Vite 8.3.6; the existing JavaScript bundle size warning remains.

### How to process the reports already on screen

Restart `make run`, open the officer queue, and click **Run triage** once on each old Pending card. Once the location evidence is strong enough, matching reports collapse into one incident card and its citizen count increases. If coordinates are absent or the match is ambiguous, the existing policy sends the report to duplicate review instead of merging on address text alone.

## Follow-up: citizen submission pipeline and officer visibility

### Root cause

- The report form created a complaint and showed success without calling the agent orchestration endpoint. Duplicate resolution and department routing therefore never ran for browser submissions.
- New complaints start with no department. The officer API's default department queue excluded those unrouted reports.
- The existing concurrent duplicate regression exposed a second dispatch call racing against the same work order before its external ID had been persisted.

### Delivered

- The report form now starts orchestration after the complaint is saved, shows distinct processing/review/failure states, and offers a processing retry without creating another complaint.
- The default officer department queue includes unrouted reports; explicit department filters remain scoped.
- Work-order dispatch now holds the database intake mutex through external-ID persistence so concurrent linked reports reuse one dispatch.
- Updated `docs/learn/04-agent-pipeline.md` with the browser submission and triage flow.

### Verification

- Added the unrouted-report officer queue regression first; it failed before the service fix and passed afterward.
- `pytest tests\test_pipeline_agents.py tests\test_officer_admin.py tests\test_phase7_verification.py -q --tb=short --disable-warnings` returned `20 passed, 16 warnings in 15.33s`.
- `npm run build` completed with Vite 8.3.6; the existing >500 kB bundle warning remains.

### Boundaries

- A citizen's dashboard remains owner-scoped. A second citizen's original report will not appear in the first citizen's private report list; linked reports share an incident tracker.
- Reports without enough location evidence may be sent to the officer duplicate-review queue instead of being automatically linked.

## Follow-up: Windows launcher and home page polish

### Delivered

- Added a PowerShell `run.ps1` that starts backend and frontend together with mock providers and a SQLite database in `%TEMP%`.
- Updated port handling so an existing listener is reused and the missing service can still start.
- Added a `Makefile` `run` target and installed GNU Make 4.4.1 with `winget`; reopen PowerShell once so its PATH refreshes.
- Refined the landing page copy and spacing, and removed unsupported performance/provider/agent-count claims.
- Added [the launcher and UI walkthrough](08-local-run-and-ui.md).

### Verification

- `npm run build` completed successfully with Vite 8.3.6. Vite still reports the JavaScript bundle exceeds 500 kB.
- PowerShell parser accepted `run.ps1`.
- Running the installed Make executable with the `run` target started both services; the frontend returned HTTP 200 and the backend root reported `online`.
- No tests were added or run for this UI/launcher-only change.

### Limits

- The already-open PowerShell session had a stale PATH after installation; a new PowerShell session resolves `make` from the installed user PATH.
- The build-size warning remains.

## Latest completed phase: Phase 8 — Explanation pack and final polish

### Delivered

- Added `docs/learn/README.md`, a consolidated project explanation and learning sequence.
- Added 50 grouped viva/interview questions with answers, `docs/learn/glossary.md`, and a roughly four-minute `docs/learn/demo-script.md`.
- Replaced the Phase 0-only traceability table with a final Met/Open table covering the problem statement, duplicate-report constraint, and phase deliverables.
- Rewrote the root README to remove stale claims about a 20-phase completion plan, active rate limiting, and a non-existent graph node. Added limitations for in-memory checkpointing, simulated connectors, synthetic evaluation, and unmeasured scale.
- Marked the Phase 0 system map as historical and corrected the Phase 4 pipeline guide's outdated provisional-incident description.
- Ran `npm audit fix`; the lockfile now resolves the audited frontend dependency tree with no reported vulnerabilities. `package.json` remains the declared dependency range source.

### Final verification in this session

From `backend/`:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=short --disable-warnings
```

Result: `134 passed, 55 warnings in 26.94s`.

The in-memory evaluator check returned **synthetic** dataset counts of 200 total, 160 calibration, and 40 held out; selected thresholds were 0.66 auto-link and 0.58 review. Fused held-out precision/recall/F1 were 1.000/0.850/0.919. This reproduces the existing synthetic report and is not a production metric.

The one-command **synthetic** demo reported five preserved reports across four channels, one incident, one work order, and five reporters notified; `1 passed, 6 deselected in 3.65s`.

From `frontend/`:

- `npm ci` completed using the lockfile; it initially reported three high-severity advisories.
- `npm audit fix` updated eight resolved packages; `npm audit` then reported `found 0 vulnerabilities`.
- `npm run build` passed with Vite 8.3.6. It still warns that the minified JavaScript chunk exceeds 500 kB.
- `npm run lint` exited successfully with existing React purity/effect/dependency warnings; no lint errors were reported.
- The local Markdown link check covered nine files and found no missing local links.

### Remaining open items

- Production-scale load evidence, independent security audit, live channel connectors, municipal dispatch integration, and real labeled duplicate evaluation remain open.
- The frontend lint warnings and large bundle warning remain for future UI/build optimization work.
- LangGraph still uses in-memory `MemorySaver`; restart loses paused graph state.

See [the Phase 8 learning index](README.md), [viva questions](viva-questions.md), [glossary](glossary.md), [demo script](demo-script.md), and [final traceability](requirements-traceability.md).

## Latest completed phase: Phase 7 — End-to-end verification, privacy, and robustness

### Delivered

- Added tests-first synthetic end-to-end verification for five reports across four channels, varied wording, and photo hashes. Reports arrive sequentially; the scenario verifies one canonical incident, one work order, five preserved complaints, and five reporters with delivered notification records.
- Folded an empty provisional incident into the canonical incident after auto-linking. Superseded link evidence records the retired provisional incident ID; original complaint and media records remain intact.
- Added a conservative officer-review rule when pHash evidence strongly conflicts, even if the fused score would otherwise auto-link.
- Required authentication and ownership/staff checks for complaint reads and lists, agent state/orchestration, stored AI analysis, reanalysis, report triage, and resolution verification. Resolution verification now requires officer/admin and uses the authenticated officer ID.
- Made complaint title, description, and category immutable through the update API; updated the former test that expected citizens could overwrite source evidence.
- Added optional per-citizen webhook idempotency keys with a unique database index and Alembic revision `0006_phase7_hardening`.
- Added image-byte verification and safe AI-provider failure fallback to officer review.
- Added `backend/scripts/run_phase7_demo.py`, `backend/tests/test_phase7_verification.py`, and `docs/learn/07-verification.md`.

### Verification

From `backend/`, in PowerShell, using the existing Phase 0 virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=short --disable-warnings
```

Result: `134 passed, 55 warnings in 23.42s`.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\run_phase7_demo.py
```

Actual synthetic demo counts: 5 reports preserved, 4 channels, 1 incident, 1 work order, and 5 reporters notified; `1 passed, 6 deselected in 3.75s`. AI is mock and delivery/dispatch calls are replaced with a local deterministic fake; no live provider was called.

### Limitations carried forward

- LangGraph still uses `MemorySaver`: a restart loses paused graph state although committed operational data remains in SQL.
- The concurrency lock is a prototype correctness mechanism; PostgreSQL lock contention and performance are not verified here.
- Image validation does not provide malware/content scanning for every supported media type.
- `Idempotency-Key` is optional; external channel providers need stable values to gain retry safety.
- The five-report counts are synthetic and are not production accuracy metrics.

See [`07-verification.md`](07-verification.md) for the walkthrough, failure boundaries, evidence, and limitations.

## Latest completed phase: Phase 6 — Officer review and feedback loop

### Delivered

- Added Alembic revision `0005_officer_duplicate_review` and persisted review-case and immutable officer-decision/label tables.
- Wired grey-zone outcomes from the agent action node into the durable queue. Pending reports are held for officer review without creating or dispatching a new work order.
- Added an officer-only review API and React page with side-by-side reports, photos, location/map previews, signal breakdown, and confirm/reject/merge/split actions.
- Kept link history when an officer confirms, splits, or merges. A confirmed match to a resolved incident creates a recurrence incident; a rejected match gets its own active work order.
- Added duplicate operations analytics computed from actual active report links, work orders, pending cases, and independent officer labels.
- Added `scripts/recalibrate_duplicate_thresholds.py`; it prints current versus proposed thresholds using persisted officer labels and never applies a change.
- Added `docs/learn/06-officer-review.md` and offline tests for queue contents, all decision paths, recurrence policy, work-order consolidation, action-node queueing, metrics, RBAC, and migration head.

### Verification

From `backend/`, using the existing Phase 0 virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_officer_duplicate_review.py tests\test_pipeline_agents.py tests\test_incidents.py tests\test_analytics.py -q --tb=short
```

Result: `11 passed, 5 warnings in 4.63s` for the final focused review suite. The complete backend suite also passed:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=short
```

Result: `127 passed, 42 warnings in 19.83s`. Warnings are existing pytest testpaths/asyncio notices, Pydantic namespace warnings, and JWT `utcnow()` deprecation warnings.

### Remaining limitations

- Work-order merge/cancel behavior only updates Namma Civic database rows; there is no external municipal provider cancellation command.
- Map previews use OpenStreetMap and require browser network access.
- Officer-derived threshold changes are report-only; they are not automatically applied.

## Previous completed phase: Phase 5 — Follow-up and citizen awareness

### Delivered

- Added Alembic revision `0004_incident_follow_up` for incident priority, incident timeline events, reporter channel preferences, and per-channel notification delivery records.
- Added a privacy-limited incident tracker API and an authenticated report-to-tracker endpoint with ownership checks.
- Added SMS/email preference endpoints, per-reporter fan-out on incident changes and verified resolution, and idempotency keys for recorded delivery attempts.
- Moved the scheduled SLA scan to active incidents. Escalations update incident and work-order priority and are audited on the incident timeline.
- Added reporter dispute/reopen handling, including active-link ownership validation, audit, and a queued work order when no active order remains.
- Added a tracker/preferences/dispute card to complaint detail and `docs/learn/05-follow-up.md`.
- Added offline tests first for public-field privacy, preference-aware fan-out, failure persistence, incident SLA, dispute authorization, API routes, and migration presence.

### Verification

From `backend/`, using the existing Phase 0 virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_incident_followup.py -q --tb=short
```

Result: `8 passed, 4 warnings in 3.96s`.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=short
```

Result: `116 passed, 39 warnings in 18.77s`. The first full run exposed one stale assertion expecting migration head `0003_duplicate_detection`; it was updated to verify the Phase 5 `0004_incident_follow_up` head and tables, then the full suite passed. Warnings include existing Pydantic namespace/JWT deprecations, pytest's testpaths notice, and pytest-asyncio's unset loop-scope notice.

### Remaining limitations

- Real SMS/email delivery semantics depend on the production provider. The local mock is deterministic; the email adapter cannot guarantee provider-side exactly-once delivery.
- Failed deliveries are recorded but not automatically retried by a worker.
- SLA deadlines are simple elapsed-hour rules based on incident creation time, not department calendars or holidays.
- The public tracker is intentionally accessible by incident ID and returns only aggregate/public fields.
- Phase 4's in-memory graph checkpointer decision remains open: paused graph state is lost on restart, while SQL complaint/incident state remains.

## Earlier completed phase: Phase 4 — Agent pipeline integration

### Delivered

- Added graph stages for vision findings, report-count priority, SLA monitoring snapshot, and optional resolution verification; corrected README claims to describe the real 10-node workflow and its thin service wrappers.
- Updated action processing to recompute duplicate results while holding a database serialization lock, write the selected report link, persist/reuse one work order per incident, and append a complaint timeline entry.
- Linked reports reuse the incident work order and notify the report owner using that user's saved phone or email. Dispatch and persistence failures return failure states instead of reporting successful dispatch.
- Added a stable work-order idempotency key to the in-process civic MCP adapter; local retries resolve to the same external work-order ID.
- Added offline tests for two simultaneous synthetic reports, retries, correct recipient, graph stages, priority rule, and failure handling.
- Added `docs/learn/04-agent-pipeline.md` with a lifecycle diagram and the real boundaries.

### Verification

From `backend/`, using the existing test virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_pipeline_agents.py::test_action_links_duplicate_and_reuses_incident_work_order -q --tb=short
```

Result: `1 passed` on both runs (4.99s and 4.91s). This local SQLite test processes two concurrent synthetic reports and retries an action; the reports share one active incident link and one work order.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests -q
```

Result: `108 passed, 36 warnings in 43.95s`. Warnings are the existing Pydantic namespace and JWT UTC deprecations, plus pytest-asyncio's unset loop-scope notice.

### Remaining decision and limitations

- The graph still uses `MemorySaver`. A restart loses state/checkpoint for a paused approval; complaint, incident, and link records remain in SQL, but no automatic graph-state reconstruction is implemented. The user must decide whether to add a persistent checkpointer.
- The SLA service still scans complaints, not incidents.
- The global DB lock is a correctness-first prototype boundary; production PostgreSQL behavior and contention need deployment verification.
- Phase 7 folds an empty provisional incident into the canonical incident and records the retired ID on superseded link evidence; the synthetic end-to-end scenario covers this behavior.

## Previous completed phase: Phase 3 — Duplicate detection

### Delivered

- Added bounded SQL candidate retrieval over indexed incident coordinates and a separate deterministic scoring engine with best-match ranking, three outcomes, bridge handling, time/status eligibility, and fail-to-review behavior.
- Added token Jaccard, character 3–5-gram cosine similarity, local pHash through pinned `ImageHash==4.3.1`, distance/category/time/place signals, and held-out synthetic calibration.
- Added Alembic revision `0003_duplicate_detection`: nullable media pHash, location confidence/accuracy, and `Incident.recurrence_of_incident_id`; accessible local legacy photos are hashed during migration.
- Added recurrence persistence helper. It creates a new incident, points it to the resolved incident, and supersedes the provisional report link while retaining the original link audit row.
- Added the 200-pair labeled synthetic dataset at `backend/data/synthetic_duplicate_pairs.json` and `docs/learn/03-duplicate-detection.md`.
- Resolver outcomes are now surfaced in graph state and officer-review outcomes route to the current human approval step. Full end-to-end link/work-order/notification integration remains Phase 4 work.

### Verification

From `backend/`, using the existing test virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_duplicate_detection.py tests\test_media_phash.py tests\test_incidents.py -q
```

The final focused tests are included in the full backend suite below.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests -q
```

Result: `99 passed, 36 warnings in 53.07s`. Warnings are existing Pydantic namespace and JWT UTC deprecations.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\evaluate_duplicate_detection.py
```

Result: 200 synthetic pairs; 160 calibration and 40 held-out test pairs; selected auto-link threshold `0.66`, review threshold `0.58`; held-out fused precision `1.000`, recall `0.850`, F1 `0.919`. Review candidate recall was `0.900` and precision `0.545`. See the learning document for each signal and ablation result.

`pip check` returned `No broken requirements found.`

### Important boundaries

- Evaluation numbers are synthetic, small-sample results and are not claims about production performance.
- The graph reports a recurrence target; Phase 4 still needs to apply the resolver outcome as part of the complete intake/work-order transaction.
- Hash backfill can only hash image files still accessible in local uploads; other legacy media remains `NULL`.
- The Vercel requirements file documents a 50 MB deployment limit; the bundle size after adding ImageHash/SciPy was not measured and must be checked before deployment.

## Previous completed phase: Phase 2 — Channel normalization

### Delivered

- Added `backend/app/channels/` with a validated `CanonicalReport` and adapters for existing `web`, `mobile`, `voice`, and `whatsapp` channel values.
- Added offline deterministic tests using an injected fake geocoder.
- Added `docs/learn/02-channels.md` with synthetic channel examples and implementation limits.
- No schema change or migration was needed. The adapter is not yet connected to complaint persistence or the LangGraph.

### Verification

From `backend/`, with the existing phase test virtual environment:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests\test_channels.py -q
```

Result: `10 passed in 2.28s`.

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest tests -q
```

Result: `79 passed, 36 warnings in 16.47s`. Warnings include existing Pydantic namespace and JWT UTC deprecations.

## Historical next-step note recorded before Phase 4

### Verified starting point

- Phase 3 has replaced the first-match complaint scan with bounded incident retrieval and a score breakdown. `backend/app/deduplication/engine.py` is pure; `repository.py` owns SQL candidate retrieval.
- Phase 1 incident, report-link and work-order models remain the persistence basis. `ComplaintService` still creates a provisional incident/link before the graph runs; Phase 4 must ensure the resolver's selected result replaces/supersedes that provisional association transactionally and only dispatches work for eligible new incidents.
- Media pHash is stored when local photo files are accessible; remote object storage is not supported by the current local path resolver.
- Phase 3 design gate is complete and approved. Do not reopen it unless new evidence warrants a material design change.

### Decisions carried forward

- Reports arriving after an incident is resolved should form a new incident by default.
- A report that appears to bridge existing incidents goes to officer review.
- Officer disagreement should be recorded and reassigned with link history/audit.
- Do not make live LLM calls without first stating an approximate call count and receiving approval. The duplicate engine and its tests have deterministic offline behavior.
- Phase 4 must preserve the approved resolved-issue recurrence rule and make each report's final link and incident work order idempotent.
