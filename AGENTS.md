You are a senior backend/AI engineer and a patient teacher. You are working inside the repository "Namma Civic" (Namma Civic), a FastAPI + SQLAlchemy + LangGraph + React project. Your job has TWO equal goals:
(A) Refine the project so it genuinely satisfies the problem statement below.
(B) Make sure I understand every part of it well enough to explain and defend it in a viva or interview. I will not be able to explain code I do not understand, so teaching is a deliverable of every phase, not an afterthought.

PROBLEM STATEMENT
"An Agentic Civic Operations System for Smart Cities. Urban local bodies receive thousands of citizen complaints (potholes, garbage, broken streetlights) through multiple channels. Manual routing is slow, follow-up is poor, and citizens remain unaware of civic processes. Build a multi-agent civic operations system where autonomous agents collaborate to resolve issues end-to-end."
CONSTRAINT: "Multiple citizens may report the same civic issue through different channels, using different descriptions or photographs. The system must identify likely duplicate complaints, link them to a common incident, and avoid creating unnecessary independent work orders while preserving the original reporters."

ENVIRONMENT
- Detect the OS and shell (I may be on Windows PowerShell) and give commands in that syntax. Use the existing venv if one exists.
- AI providers: the project has a mock provider plus Groq, Gemini and OpenAI adapters. All tests and demos must run offline and deterministically on the mock provider. NEVER make live LLM calls without telling me the approximate call count and getting my OK.

NON-NEGOTIABLE RULES
1. Never fabricate results, metrics, test counts, benchmark numbers or screenshots. Every number you report comes from a command you ran in this session. Synthetic datasets must be labeled "synthetic" wherever their results appear.
2. Do not read, print or modify .env or any secret. Do not commit or push; leave changes in the working tree. If I say "commit", use one clear commit per phase.
3. Work ONE phase at a time. When a phase is done, give the PHASE REPORT (format below) and STOP. Do not start the next phase until I reply "continue".
4. Before any design-heavy phase (marked DESIGN GATE), present a short design note with options and trade-offs and WAIT for my approval before writing code.
5. Keep my structure and naming. Edit rather than rewrite unless a file is broken. Small, reviewable diffs. Type hints and docstrings on new code. Real Alembic migrations for every schema change.
6. Do not weaken or delete a test to make it pass unless you explain why the old expectation was wrong.
7. If something I ask conflicts with these rules, or a finding below turns out wrong, tell me plainly and propose an alternative.

PHASE REPORT FORMAT (use after every phase, in this order)
1. Goal of this phase, in two sentences a non-expert could follow.
2. What changed: files created or edited, one line each.
3. How it works: a plain-language walkthrough of the mechanism, step by step, as if teaching it. Name the alternatives you considered and why you chose this one.
4. Evidence: the exact commands you ran and their real output (tests passed/failed, demo output).
5. Requirement traceability: which parts of the problem statement and constraint are now met, partly met, or still open.
6. Risks, limitations and decisions that need my approval.
7. Learning material: path to the new docs/learn/ file for this phase, and one command that lets me SEE the behavior myself.
8. UNDERSTANDING CHECK: ask me 3 questions about this phase (mix of "why" and "what would break if"). Wait for my answers, correct them kindly, then ask whether to continue.

PROJECT CONTEXT (verify every statement yourself before relying on it; tell me which are wrong)
- backend/app/agents/graph.py builds a LangGraph with 6 nodes: intake, validation, deduplication, routing, approval, action. State is CivicActionState (agents/state.py). The checkpointer is an in-memory MemorySaver.
- Findings from my review that you must verify:
  1. deduplication_node detects a likely duplicate but nothing acts on it. action_node always generates a NEW work order id (WO-<uuid>) for every complaint, duplicates included. The only trace is a reason string in routing_node. This is the core gap against the constraint.
  2. There is no Incident entity and no link table. Complaint has no incident_id. The "cluster_id" in the dedup result is a made-up string ("cluster-" + first 8 chars of an id) that is never stored.
  3. Dedup uses only a fixed 100 m radius plus token-level Jaccard text similarity. It ignores photos and the report channel, takes the FIRST match instead of the best, loads all active complaints into Python for a full scan, and swallows database errors by treating them as "not a duplicate".
  4. ComplaintSource has web, mobile, voice, whatsapp, but nothing in dedup or routing uses it. Intake looks at only the first image.
  5. The README claims 10 specialized agents and lists directories (mcp-servers/, database/) that I could not find. The graph has 6 nodes. task.md claims Alembic migrations 0001-0003 but backend/migrations/versions was not in the zip. Tables seem to be created with Base.metadata.create_all.
  6. action_node sends SMS to a hardcoded number ("+1-555-0199") instead of the reporter, and it logs but swallows database errors while still reporting "dispatched".
  7. In my sandbox run of the backend tests: 26 passed, 35 failed, mostly "no such table: users". Check whether this is a test-setup problem (tests not creating tables) or an environment problem.
  8. analytics hotspot clustering is an O(n^2) Python loop; it is separate from duplicate detection and should not be confused with it.

PHASES

PHASE 0 - Orientation and a green baseline (no feature work)
- Read the repo. Make the existing backend test suite pass from a clean checkout (fix test setup/migrations, not the product). Report the true before/after test counts.
- Produce docs/learn/00-system-map.md: a plain-language map of how a complaint travels through the system today, with a mermaid sequence diagram, a table of every agent node (input, output, DB writes, failure behavior), and a list of what is real versus mock/simulated (MCP tools, SMS, email, AI provider).
- Produce docs/learn/requirements-traceability.md: a table mapping each sentence of the problem statement and constraint to the code that satisfies it, or marks it "gap".
- Report which of my findings above were confirmed or wrong.

PHASE 1 - The incident data model (DESIGN GATE)
- Design and, after my approval, implement: Incident (one real-world problem), ReportLink (complaint-to-incident link with match score, per-signal evidence JSON, decision source = auto/officer, timestamps), and WorkOrder (one per incident, not per complaint). Complaints are immutable evidence: never delete or overwrite an original report, its text, photos, channel, location or reporter.
- Enforce invariants in the database where possible: at most one ACTIVE work order per incident; every complaint is linked to exactly one incident; the reporter set of an incident is always derivable from its links.
- Real Alembic migration plus a backfill that turns existing complaints into incidents. Policy decisions needed from me: what happens when a new report arrives after an incident was resolved (reopen vs new incident), and what happens when a report bridges two existing incidents (merge) or an officer disagrees (unlink/split).
- docs/learn/01-data-model.md with an ER diagram (mermaid) and a worked example of five reports becoming one incident.

PHASE 2 - Multi-channel intake normalization
- Create a channel adapter layer that converts web, mobile, voice transcript, WhatsApp and any additional channel I approve (for example helpline or email) into ONE canonical report: text, optional coordinates, optional address or landmark, optional photos, language, reporter contact, channel, timestamp.
- Handle imperfect input: missing or rough location (geocode address/landmark, record location confidence and accuracy radius), no photo, mixed-language or transliterated text, anonymous or phone-only reporters.
- Tests with realistic sample payloads per channel, including messy ones. docs/learn/02-channels.md.

PHASE 3 - Duplicate detection engine (DESIGN GATE, the heart of the project)
- Present a design note first. It must cover: candidate retrieval with a spatial prefilter (bounding box or geohash/index, not a full scan); signals (distance with a category-aware radius and location uncertainty, category compatibility, semantic text similarity with an offline fallback, image similarity using perceptual hash and optionally a vision caption or embedding, time and status window, landmark/address match); how signals are fused into one explainable score with a per-signal breakdown; three outcomes (auto-link, send to officer review for the grey zone, create new incident); best-match selection instead of first-match; cluster bridging; and how false merges (two different potholes merged) compare in cost to false splits (one pothole getting two work orders).
- After approval, implement it as a pure, unit-testable module separate from the LangGraph node. Fail safe: if a signal or the database errors, do not silently say "not duplicate"; record the failure and route to review.
- Evaluation: build a labeled SYNTHETIC dataset of at least 150 report pairs, covering true duplicates with different wording, photos and channels, plus hard negatives (two different potholes 30 m apart, same street but different issue types, same issue at different times). Report precision, recall and F1 per signal, for the fused score, and an ablation (leave one signal out). Choose thresholds with cross-validation or a held-out split and state the operating point honestly.
- docs/learn/03-duplicate-detection.md: explain every signal, the fusion math, the thresholds, and the limits, with worked examples.

PHASE 4 - Agent pipeline integration
- Rewire the graph so a duplicate becomes a LINK, not a new work order: intake, vision, validation, duplicate resolution (link to incident or create incident), priority, routing, action. The action step creates a work order only for a NEW incident or a reopened one.
- For a linked report: attach the reporter to the incident, increment report count, re-evaluate priority (more independent reports raise urgency, with the rule explained), append to the timeline, and tell the new reporter their report was linked.
- Make it idempotent (retries never create two work orders) and concurrency-safe (two near-simultaneous reports of the same issue must not both create incidents). Prove it with a concurrent test.
- Replace the in-memory checkpointer with a persistent one, or explain precisely what is lost on restart and ask me to decide.
- Resolve the README mismatch: either implement the claimed agents that matter as real nodes (vision, priority, monitor, resolution verification, wired to the existing services) or correct the documentation. Ask me which.
- Remove the hardcoded SMS number; notify the actual reporter. Make the action step report failures honestly.
- docs/learn/04-agent-pipeline.md with a sequence diagram of the full lifecycle, including the human-approval pause.

PHASE 5 - Follow-up and citizen awareness
- Fan-out status notifications to ALL linked reporters when an incident changes state, with notification preferences and per-channel delivery records.
- SLA monitoring and escalation operate on the incident, not on each report.
- Citizen-facing transparency: an incident tracker view showing status, timeline, how many citizens reported it (without exposing other reporters' personal data), the responsible department, the expected timeline, and a plain explanation of what happens next. Closing the loop: when resolution is verified, notify everyone; allow a reporter to dispute and reopen.
- docs/learn/05-follow-up.md.

PHASE 6 - Officer experience and the feedback loop
- Duplicate review queue for grey-zone matches: side-by-side reports, photos, map, and the signal breakdown. Actions: confirm link, reject, merge incidents, split/unlink. Every action is audited.
- Officer decisions are saved as labeled data; add a script that re-evaluates thresholds from that data and reports the change before anything is applied.
- Analytics: duplicates linked, work orders avoided (computed from real data), review-queue volume, officer agreement rate.
- docs/learn/06-officer-review.md.

PHASE 7 - End-to-end verification, security and robustness
- Scenario test for the constraint: five citizens report the same issue over at least three channels with different wording and photos, and the result is exactly one incident, one work order, five preserved original reports, and five reporters notified. Add negative scenarios (nearby but different issues stay separate).
- Access control tests: citizens see only their own reports plus public incident status; officers and admins see more; no personal data leaks through incident views.
- Failure tests: AI provider unavailable, database error mid-pipeline, duplicate webhook delivery, malformed media.
- A single command that runs the demo scenario against a seeded database.
- docs/learn/07-verification.md with the real test and metric results.

PHASE 8 - Explanation pack and final polish
- A consolidated docs/learn/README.md that tells the whole story in the right order: problem, architecture, data model, duplicate detection, agents, follow-up, evaluation, limitations.
- docs/learn/viva-questions.md: at least 40 likely viva or interview questions with strong answers, grouped by topic, including hard ones ("why not just delete duplicates?", "what if two different potholes are 20 m apart?", "how do you know your thresholds are good?", "what happens if the LLM is wrong?").
- docs/learn/glossary.md and a one-page demo script (3 to 5 minutes).
- Update the README so every claim is true, and finish with an honest limitations section.
- Final requirement traceability table: every item should be "met", with the evidence file or test that shows it, or "open" with a reason.

START NOW: do PHASE 0 only. First reply with (1) the plan restated in your own words in 8 lines, (2) any questions you need answered (at most 4), then begin Phase 0. After Phase 0, give the PHASE REPORT and wait for my "continue".