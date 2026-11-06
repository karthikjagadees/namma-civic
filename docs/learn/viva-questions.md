# Namma Civic viva and interview questions

Answers describe the current repository. This is a prototype; synthetic tests and mock integrations are not production evidence.

## Problem and architecture

### 1. What problem does Namma Civic address?

It organizes citizen reports about civic problems, tries to identify reports that concern the same issue, and provides an incident-level follow-up record. The key constraint is to reduce duplicate operational work without deleting the individual reports or losing their reporters.

### 2. What does “agentic” mean in this implementation?

It means a LangGraph workflow coordinates named stages and can pause for an officer. It does not mean every stage is an independent AI model. Several nodes are deterministic logic or thin wrappers around existing services.

### 3. What technologies are used?

FastAPI exposes the API; SQLAlchemy and Alembic persist and evolve the relational schema; LangGraph coordinates workflow state; React and Vite provide the frontend. AI and tool integrations have mock paths for offline operation.

### 4. What happens after a citizen submits a report?

The API stores the complaint and evidence metadata and creates its initial incident/link. The graph runs intake, vision forwarding, validation, candidate matching, routing, priority, optional officer approval, and action. Monitoring and optional resolution verification follow.

### 5. Why use named graph nodes?

They make the order and state transitions visible, let policy route uncertain work through human review, and give tests clear stage boundaries. The tradeoff is extra orchestration complexity compared with a single service function.

### 6. Is every node an AI agent?

No. The graph has named workflow nodes, but routing, priority, vision forwarding, monitoring, and some verification are service wrappers or deterministic rules. The README now describes that distinction.

### 7. What does the system not prove yet?

It does not prove real-city accuracy, thousand-report throughput, provider delivery guarantees, a live municipal dispatch integration, or production security. Those require representative data and operational testing.

## Data model and invariants

### 8. What is the difference between a Complaint and an Incident?

A Complaint is one citizen's submitted report and evidence. An Incident is the shared operational issue that may be supported by multiple complaints.

### 9. Why not delete duplicate complaints?

Each report is independent evidence and represents a citizen who deserves attribution and updates. Deleting it destroys provenance, reporter linkage, and an audit trail.

### 10. What does ReportLink store?

It connects one complaint to an incident and records score/evidence, decision source, timestamps, and link history. Old links remain when an officer reassigns a report.

### 11. How is the reporter set for an incident obtained?

By joining its active ReportLink rows to their Complaint rows and reading each complaint's citizen ID. The incident does not need a duplicate copy of that list.

### 12. How is one active work order enforced?

A partial unique index allows only one work order per incident whose status is active. Completed and cancelled orders remain as history.

### 13. How does the database preserve a report's original content?

The update API rejects changes to submitted title, description, and category. The duplicate workflow changes link and incident records, leaving the source complaint and its media associated with the original reporter.

### 14. What is an incident recurrence?

When evidence strongly matches a resolved incident, policy creates a new incident and sets `recurrence_of_incident_id` to the resolved incident. The old resolved record stays resolved for historical accuracy.

## Duplicate detection

### 15. How does candidate retrieval work?

The repository builds a geographic bounding box, queries eligible incidents in SQL, and caps the result count. This avoids loading every complaint and scoring a full table scan in Python.

### 16. Why use a bounding box before exact distance?

The box is a cheap, conservative filter that narrows database work. The scoring step then calculates distance more precisely for each retrieved candidate.

### 17. Which signals contribute to a match?

Distance, category compatibility, token overlap, character n-gram similarity, photo pHash similarity, time proximity, and address/landmark overlap. Each score is returned for explanation.

### 18. What does token Jaccard similarity measure?

It compares sets of words: the number of shared words divided by the number of distinct words across both texts. It is simple and explainable, but word order and meaning are mostly ignored.

### 19. What do character n-grams add?

They compare short overlapping character sequences, which can tolerate some misspellings or suffix differences. They can also consider unrelated words similar and do not solve cross-language semantic matching.

### 20. What does perceptual hashing do?

It reduces an image to a compact representation of its broad visual pattern. Similar hashes suggest similar-looking images; they do not identify objects or prove two photos depict the same pothole.

### 21. When can pHash fail?

Different scenes with similar layouts may match, while a severe crop, viewpoint change, lighting change, or different repair state may reduce similarity for the same place. A human or richer vision system may be needed.

### 22. How are missing signals handled in the fused score?

The score averages the available weighted signals and renormalizes by their available weight. An absent photo is not treated as a zero similarity. Missing coordinates trigger officer review rather than text-only auto-linking.

### 23. What are the three resolver outcomes?

`auto_link` attaches the report to one strong active candidate; `officer_review` asks a human to decide; `new_incident` creates a separate operational record. A strong match to a resolved issue is handled as a recurrence, a new incident with a recurrence link.

### 24. Why select the best candidate rather than the first one?

Database ordering is not evidence of the best match. Ranking by score and deterministic tie-breakers makes the decision depend on the strongest candidate and makes repeated runs more predictable.

### 25. What is a cluster bridge and why is it reviewed?

A report may score as a match to two existing incidents. Automatically choosing one could merge separate civic jobs, so the system sends that ambiguity to an officer.

### 26. What if two different potholes are only 20 metres apart?

Distance alone should not settle the decision. Category, wording, photo, place, time, and location uncertainty contribute. Strongly conflicting photo evidence is a review reason. No heuristic guarantees correct separation in every case, so thresholds and hard negatives need real labeled evaluation.

### 27. How were the thresholds chosen?

They were selected from a deterministic held-out synthetic evaluation described in `03-duplicate-detection.md`. That supports reproducibility on the authored data, not a claim that the same operating point is calibrated for a real city.

## Workflow and operations

### 28. What does the vision node do?

It exposes vision analysis already returned by intake as its own graph stage. It does not make an additional model call.

### 29. How does priority respond to report volume?

The priority node counts distinct linked reporters and raises the base priority by one level for each group of three additional reports after the first, capped at critical. Critical priority can require officer approval.

### 30. What makes action idempotent?

The action node rechecks candidates under a database serialization lock and queries for an existing active work order before creating one. Stable IDs and persisted records let retries reuse the existing incident/order.

### 31. What prevents two simultaneous reports from creating separate incidents?

The action step serializes the database decision and rescans after obtaining the lock. A concurrent test exercises this behavior in the local test setup. Production database contention still requires deployment testing.

### 32. What happens if AI intake throws an error?

Intake produces a low-confidence fallback with the submitted category hint and a provider-failure flag. Routing requires officer review rather than pretending the model succeeded.

### 33. What happens if database persistence fails during action?

The action result is marked failed and does not claim that dispatch succeeded. The offline failure test injects a deterministic session failure; it is not a crash-recovery simulation.

### 34. What does the in-memory checkpointer mean?

LangGraph's `MemorySaver` holds checkpoints in process memory. Restarting the process loses paused graph state; committed reports, links, incidents, work orders, and timelines remain in SQL. Automatic graph reconstruction after restart is not implemented.

### 35. How does follow-up notify multiple reporters?

The follow-up service derives recipients from the active report links and each reporter's preferences, then persists channel delivery records. Tests use local fake providers, so they verify application behavior and not actual carrier/email delivery.

### 36. What does the citizen tracker expose?

It exposes incident operations such as status, timeline, report count, department and next-step explanation while omitting reporter contacts and private report text. The tracker can be looked up publicly by incident ID.

### 37. How does SLA monitoring work?

The scheduled worker scans incidents and invokes incident-level SLA calculation/escalation. The graph monitoring node records a snapshot and delegates escalation to that worker. These are prototype rules, not an approved municipal service policy.

### 38. What is resolution verification in this project?

It is an existing heuristic service that inspects resolution notes and an optional image URL, updates the linked incident when deemed verified, and can notify linked reporters. It is not a trained visual before/after model.

## Security, evaluation, and limitations

### 39. How are private complaints protected?

Complaint read/list and report-specific AI/agent paths require authentication and ownership or staff authorization. A foreign citizen report ID returns not found. Tests cover owner, other citizen, officer, and public tracker behavior.

### 40. What information is hidden from public incident views?

Reporter IDs and names, email/phone, and private complaint descriptions are omitted. The incident tracker provides operational status and aggregate counts rather than exposing the linked report contents.

### 41. Is rate limiting implemented?

No active rate-limit middleware is wired into the FastAPI app. A rate-limit setting exists in configuration, but that alone does not enforce a limit; the README now calls this out.

### 42. Is the whole system offline?

Tests and the demo force the mock AI provider and mock tool behavior. The application also contains live AI adapters and may use external services if configured for them. The demo does not make those live calls.

### 43. What does synthetic evaluation tell us?

It tells us how the implemented scorer performed on the authored pairs and makes changes reproducible. It cannot establish how real residents phrase reports, how local images vary, or how the system performs on production data.

### 44. Why report precision and recall separately?

Precision describes how often an automatic match is correct; recall describes how many true duplicates are found. A conservative system can have high precision and still miss duplicates, so the operating tradeoff must be explicit.

### 45. What is ablation and what does it show here?

Ablation removes one signal and reevaluates the same labeled set. It can show whether a signal helped that particular dataset, but a tiny synthetic set may be biased and cannot settle whether the signal is useful in production.

### 46. How could thresholds improve safely?

Collect reviewed examples with signal snapshots, measure performance on separated representative data, compare proposed values with current values, and review operational impact before applying a change. The current recalibration script reports suggestions only.

### 47. What if the LLM is wrong?

The workflow treats model output as one input, not ground truth. Validation, deterministic location-aware matching, thresholds, confidence checks, and human approval constrain the effect. Provider failure routes to review, but model mistakes still need monitoring and labeled feedback.

### 48. Why not use embeddings for all text?

The approved design uses deterministic offline token and character n-gram similarity, which is inexpensive, auditable, and available without a model service. Embeddings may improve paraphrase matching but introduce a model/version dependency and need their own evaluation.

### 49. What is the difference between a false merge and a false split?

A false merge combines distinct real issues and can hide a job or misinform residents. A false split duplicates operational work. Namma Civic uses review for ambiguity and keeps source reports intact so officers can correct associations.

### 50. What is the most important next production step?

Build a privacy-reviewed evaluation set from representative local reports, label duplicate pairs with officers, and validate both accuracy and throughput. Before deployment, also review security, real provider delivery, operational recovery, and dispatch integration.
