# Final requirement traceability

Status describes the repository and evidence available at the end of Phase 8. “Met” means the requirement has implementation or test evidence in this prototype; it does not imply a production deployment. “Open” means the requirement or its production proof remains outstanding.

## Problem statement and duplicate-report constraint

| Requirement | Status | Evidence or reason |
|---|---|---|
| Civic operations system for smart cities | Met | FastAPI/React/SQL/LangGraph prototype: [system map](00-system-map.md), [architecture guide](README.md). |
| Handle civic issue categories such as potholes, garbage, and streetlights | Met | `ComplaintCategory` in `backend/app/models/complaint.py`; route and category behavior covered by backend tests. |
| Receive reports from multiple channels | Met | Channel values and normalization adapters for web, mobile, voice, and WhatsApp: `backend/app/channels/`, [channel guide](02-channels.md). |
| Live external connector for every channel | Open | Adapters normalize payloads, but this repository does not prove live ingestion from each external channel. |
| Support thousands of complaints at production scale | Open | No load test or production capacity measurement has been run. |
| Reduce manual department routing | Met | Deterministic category-to-department routing in `backend/app/agents/nodes/routing_node.py`, used by the graph and tested. |
| Improve follow-up and escalation | Met | Incident timeline, reporter fan-out, preferences, incident SLA scan/escalation, and dispute/reopen paths: `backend/app/services/incident_follow_up_service.py`, `backend/app/services/sla_service.py`, [follow-up guide](05-follow-up.md). |
| Make civic process/status visible to citizens | Met | Public privacy-limited incident tracker with status, timeline, counts, and next-step explanation: `backend/app/api/v1/incidents.py`; tested in `backend/tests/test_incident_followup.py` and `backend/tests/test_phase7_verification.py`. |
| Autonomous collaboration resolves issues end-to-end with real municipal operations | Open | Graph and persistence are implemented, but real dispatch, notification delivery, and city case-management integration are not demonstrated. The graph nodes include deterministic logic and service wrappers. |
| Preserve each citizen's original report, media, channel, location, and reporter | Met | Complaint/media records remain distinct; update API protects title, description, and category; report links retain association history. Evidence: `backend/app/services/complaint_service.py`, `backend/app/models/report_link.py`, `backend/tests/test_complaints.py`, and `backend/tests/test_phase7_verification.py`. |
| Compare differing wording, channels, and photographs for likely duplicates | Met | Engine compares text n-grams, category, pHash, time, location, and place evidence. Five-report **synthetic** scenario exercises varied wording, four channels, and stored photo hashes: `backend/tests/test_phase7_verification.py`. |
| Link likely duplicates to a common incident and avoid unnecessary active work orders | Met | Resolver action persists a shared active ReportLink and reuses one active incident WorkOrder. The five-report **synthetic** scenario asserts one incident and one work order; concurrency behavior is exercised in `backend/tests/test_pipeline_agents.py`. |
| Keep different nearby issues from being auto-merged when evidence conflicts | Met | Hard-negative test requires that two nearby pothole reports with strongly conflicting pHash evidence do not auto-link; the engine sends strong photo contradiction to review. This does not prove all nearby cases will be correct. |

## Phase deliverables

| Phase requirement | Status | Evidence or reason |
|---|---|---|
| Phase 0: readable system map, agent input/output/failure inventory, and real-vs-simulated inventory | Met | [00-system-map.md](00-system-map.md). |
| Phase 0: trace requirements and verify project findings | Met | Historical findings in [Phase 0 report](phase-0-report.md); this file reflects final requirement status. |
| Phase 0: green backend baseline | Met | Phase 0 report records baseline; final backend suite after Phase 8 is also run in this session. |
| Phase 1: Incident, versioned ReportLink, and WorkOrder model | Met | `backend/app/models/incident.py`, `backend/app/models/report_link.py`, `backend/app/models/work_order.py`, migrations `0002` onward, [data model guide](01-data-model.md). |
| Phase 1: at most one active work order per incident | Met | Partial unique index `uq_work_orders_one_active_per_incident` in WorkOrder model/migration; exercised by incident and pipeline tests. |
| Phase 1: each report linked to one active incident; reporters derived from links | Met | Partial unique active-link index and reporter queries; [data model guide](01-data-model.md), incident tests. |
| Phase 1: legacy complaint backfill | Met | Alembic `0002_incidents`; legacy migration adoption is checked in `backend/tests/test_incidents.py`. |
| Phase 1: resolved recurrence creates a new incident by default | Met | Recurrence pointer/helper and officer review path; `backend/app/services/incident_service.py`, `backend/tests/test_officer_duplicate_review.py`. |
| Phase 2: canonical channel payloads and imperfect inputs | Met | `backend/app/channels/` and [channel guide](02-channels.md), including offline normalization tests. |
| Phase 2: production geocoder/channel integrations | Open | Normalization interfaces and test fakes exist; real integrations and their service quality are not established. |
| Phase 3: bounded spatial SQL candidate retrieval | Met | `backend/app/deduplication/repository.py`; candidate retrieval tests in `backend/tests/test_duplicate_detection.py`. |
| Phase 3: explainable signals, best-match selection, and three outcomes | Met | Pure matching engine `backend/app/deduplication/engine.py` and [duplicate guide](03-duplicate-detection.md). |
| Phase 3: no text-only auto-linking for unresolved locations; failures go to review | Met | Engine and repository failure behavior in `backend/app/deduplication/`; duplicate detection tests. |
| Phase 3: synthetic labeled evaluation, held-out metrics, ablation, and threshold selection | Met | Dataset, evaluator, and explicitly labeled **synthetic** results in [03-duplicate-detection.md](03-duplicate-detection.md); `backend/scripts/evaluate_duplicate_detection.py`. Not a real-data validation. |
| Phase 3: vision caption or embedding as an additional duplicate signal | Open | Current duplicate engine uses deterministic pHash and lexical n-grams; it does not use captions or embeddings as duplicate signals. |
| Phase 4: linked report avoids a separate work order; report count raises priority | Met | `action_node`, `priority_node`, `backend/tests/test_phase7_verification.py`, and [pipeline guide](04-agent-pipeline.md). |
| Phase 4: idempotency and concurrency-safe resolution | Met | Work-order uniqueness, action-time rescan under serialization lock, optional webhook key migration, `backend/tests/test_pipeline_agents.py`, `backend/tests/test_phase7_verification.py`. |
| Phase 4: persistent graph checkpointer or exact restart explanation | Met | Restart behavior and loss boundary documented in [04-agent-pipeline.md](04-agent-pipeline.md) and [07-verification.md](07-verification.md). Current checkpointer is in-memory, not persistent. |
| Phase 4: vision, priority, monitoring, and resolution verification stages | Met | Ten-node graph and service wrappers in `backend/app/agents/graph.py` and `backend/app/agents/nodes/`; pipeline tests. |
| Phase 5: incident-wide notifications with channel preferences and delivery records | Met | `backend/app/services/incident_follow_up_service.py`, preference/delivery models, `backend/tests/test_incident_followup.py`. Provider delivery itself is simulated in tests. |
| Phase 5: incident SLA scan/escalation | Met | `SLAService.scan_incidents_and_auto_escalate` and `backend/app/workers/sla_monitor.py`; tests in `backend/tests/test_sla.py` and incident follow-up tests. |
| Phase 5: privacy-limited tracker and reporter dispute/reopen | Met | `backend/app/api/v1/incidents.py`, follow-up service, and `backend/tests/test_incident_followup.py`. |
| Phase 6: grey-zone officer review queue and audited actions | Met | Review API/service/UI, `backend/app/models/duplicate_review.py`, and `backend/tests/test_officer_duplicate_review.py`. |
| Phase 6: officer labels and report-only threshold recalibration | Met | Decision rows store labels; `backend/scripts/recalibrate_duplicate_thresholds.py` reports recommendations without applying them. |
| Phase 6: operational duplicate analytics | Met | Officer-only duplicate operations endpoint derives metrics from persisted links, work orders, cases, and labels; tests in `backend/tests/test_analytics.py` and `backend/tests/test_officer_duplicate_review.py`. |
| Phase 7: five reporters, three or more channels, varied evidence, one incident/order, preserved reports, notifications | Met | **Synthetic** run output is recorded in [07-verification.md](07-verification.md); executable scenario is `backend/scripts/run_phase7_demo.py`. |
| Phase 7: access-control and tracker privacy checks | Met | `backend/tests/test_phase7_verification.py`, complaint/agent/AI/resolution route dependencies, and incident tracker service. |
| Phase 7: AI outage, DB persistence failure, webhook replay, malformed media failure tests | Met | `backend/tests/test_phase7_verification.py` and `backend/tests/test_pipeline_agents.py`. Failures are deterministic simulations, not infrastructure chaos tests. |
| Phase 7: one-command offline seeded demo | Met | `backend/scripts/run_phase7_demo.py`; exact command/results in [07-verification.md](07-verification.md). |
| Phase 8: consolidated guide, at least 40 viva questions, glossary, and 3–5 minute demo script | Met | [Learning README](README.md), [50 viva questions](viva-questions.md), [glossary](glossary.md), [demo script](demo-script.md). |
| Phase 8: truthful root README and honest limitations | Met | Root [README.md](../../README.md); unsupported rate-limit and stale phase-completion claims removed. |
| Phase 8: independently audited security and production-scale operation | Open | No independent audit, penetration test, or load test has been run. |
