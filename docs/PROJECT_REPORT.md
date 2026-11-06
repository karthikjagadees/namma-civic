# Namma Civic — project report

This report describes the prototype as it exists in the repository, then records measurements from one local run on 6 November 2026. Duplicate-detection scores are from a **synthetic** dataset. They are not results from real Bengaluru complaints.

Commands, all from `backend/`, with mock AI and mock tools:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" -m pytest -q --tb=line --disable-warnings
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\evaluate_duplicate_detection.py
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\run_phase7_demo.py
```

## 1. What the system is

Namma Civic is a local civic-reporting prototype. A citizen files a complaint. The system keeps that complaint unchanged, decides whether it is the same real-world problem as an existing incident, and opens one work order for a new incident. A repeat report is linked to the incident that already exists.

The local demo uses SQLite, a mock AI provider, and simulated SMS, email, and dispatch. It is not a live city deployment.

## 2. How a report moves

1. The citizen submits text, a place, and an optional photo on the web form.
2. The complaint is saved first and receives a tracking ID such as `NC-BYWT-NTTN`.
3. LangGraph then runs ten stages: intake, vision, validation, deduplication, routing, priority, approval, action, monitoring, and resolution verification.
4. Deduplication returns one of three decisions: auto-link, send to an officer, or create a new incident.
5. Action creates a work order only for a new or reopened incident. A linked report reuses the open work order.
6. The citizen can open `/track` with the ID. The page shows status, department, expected time, and how many people reported it. It does not show other reporters’ names or phone numbers.

Vision does not call a second model. It forwards the image result already produced at intake. Approval can pause for a person. That pause lives in memory, so a backend restart forgets it. Saved complaints, incidents, and work orders remain in the database.

## 3. Data model

| Record | Role |
|---|---|
| Complaint | The original report. Text, photos, channel, place, and reporter are kept. |
| Incident | The real-world problem. Many complaints can point at one incident. |
| Report link | Joins one complaint to one incident, with the match score and the reason. |
| Work order | One active municipal job per incident. |
| Tracking ID | Public code `NC-XXXX-XXXX` on each complaint. Separate from the internal id. |

Schema changes are Alembic revisions `0001` through `0007`. `0002` creates incidents and backfills older complaints. `0007` adds tracking IDs and fills them for rows that already existed.

## 4. Duplicate detection

Candidates are loaded with a map bounding box, not a scan of every complaint. Each candidate gets a weighted score. Missing signals are left out of the average. A database or signal error goes to officer review. It is not treated as “not a duplicate.”

| Signal | Weight | What it measures |
|---|---:|---|
| Distance | 0.24 | Closeness inside a category radius (pothole 100 m, street light 45 m, garbage 60 m, other values in code) |
| Image pHash | 0.18 | Perceptual hash of stored photos. A near-copy, not a vision model |
| Category | 0.16 | Same issue type, with a small score for a few related pairs |
| Character n-grams | 0.14 | Spelling-level text overlap |
| Token overlap | 0.12 | Shared words |
| Address / landmark | 0.10 | Place-text match |
| Time | 0.06 | How close the report times are |

Status is a filter. Only open, in-progress, or resolved incidents inside one year are scored. The report channel is stored and is not part of the score.

Thresholds chosen on the synthetic calibration split, and stored in code:

- Auto-link at **0.66** or above
- Officer review at **0.58** or above, and below 0.66
- Below 0.58, a new incident

A near-identical photo of the same category within 20 metres can force a link. Two photos that clearly disagree block an automatic merge and go to review.

## 5. Synthetic evaluation

The evaluator wrote `backend/data/synthetic_duplicate_pairs.json`.

| Item | Count |
|---|---:|
| Labelled pairs | 200 |
| Pairs used to choose thresholds | 160 |
| Held-out pairs | 40 |
| Held-out positives | 20 |
| Held-out negatives | 20 |

These pairs are generated examples: reworded duplicates, and hard negatives such as two different potholes near each other.

### Held-out score, auto-link at 0.66

| Signal | Precision | Recall | F1 | True positive | False positive | False negative | True negative |
|---|---:|---:|---:|---:|---:|---:|---:|
| Distance | 1.000 | 0.800 | 0.889 | 16 | 0 | 4 | 20 |
| Category | 0.571 | 1.000 | 0.727 | 20 | 15 | 0 | 5 |
| Token overlap | 0.750 | 0.750 | 0.750 | 15 | 5 | 5 | 15 |
| Character n-grams | 0.800 | 1.000 | 0.889 | 20 | 5 | 0 | 15 |
| Image pHash | 1.000 | 0.750 | 0.857 | 15 | 0 | 5 | 20 |
| Time | 0.500 | 0.450 | 0.474 | 9 | 9 | 11 | 11 |
| Address / landmark | 0.500 | 1.000 | 0.667 | 20 | 20 | 0 | 0 |
| **Fused score** | **1.000** | **0.850** | **0.919** | **17** | **0** | **3** | **20** |

Reading the fused row: of 20 true duplicates, 17 were auto-linked and 3 were missed. None of the 20 non-duplicates were auto-linked.

The review band is wider, so it catches more duplicates and also more non-duplicates:

| Operating point | Precision | Recall | F1 | True positive | False positive | False negative | True negative |
|---|---:|---:|---:|---:|---:|---:|---:|
| Review at 0.58 | 0.545 | 0.900 | 0.679 | 18 | 15 | 2 | 5 |

That means most synthetic duplicates reach a human, and the review queue also contains many non-duplicates.

### Leave-one-signal-out, same 40 pairs, auto-link rule

| Signal removed | Precision | Recall | F1 |
|---|---:|---:|---:|
| Distance | 0.762 | 0.800 | 0.780 |
| Category | 1.000 | 1.000 | 1.000 |
| Token overlap | 1.000 | 0.800 | 0.889 |
| Character n-grams | 1.000 | 0.800 | 0.889 |
| Image pHash | 1.000 | 0.850 | 0.919 |
| Time | 1.000 | 0.850 | 0.919 |
| Address / landmark | 1.000 | 0.850 | 0.919 |

On this generated set, removing distance hurts the score. Removing category raises it to a perfect 1.000. Removing image, time, or address leaves the fused score unchanged. That is a warning about this synthetic set and the hand-set weights. It is not a reason to drop those signals, and it is not evidence about real streets.

## 6. End-to-end scenario

One synthetic scenario filed five reports of the same issue over four channels, with different wording and stored photo hashes. The run printed:

| Check | Result |
|---|---:|
| Reports preserved | 5 |
| Channels | 4 |
| Incidents | 1 |
| Work orders | 1 |
| Reporters with a delivery record | 5 |

The test wrapper finished as `1 passed, 7 deselected in 4.54s`. Delivery and dispatch in that run are in-process fakes. No SMS or email left the machine.

## 7. Backend test suite

`160 passed, 60 warnings in 27.65s` on Python 3.12.10, pytest 8.3.3. Warnings are library notices, not failures.

| Test file | Passed |
|---|---:|
| Auth | 13 |
| Tracking IDs | 20 |
| Duplicate detection | 18 |
| Officer duplicate review | 11 |
| Channels | 10 |
| Agents | 9 |
| AI | 9 |
| Complaints | 9 |
| Pipeline agents | 9 |
| Incidents | 8 |
| Incident follow-up | 8 |
| Phase 7 verification | 8 |
| Media perceptual hash | 5 |
| Officer and admin | 5 |
| Analytics | 4 |
| MCP tools | 4 |
| SLA | 4 |
| Health | 3 |
| Resolution | 3 |
| **Total** | **160** |

No frontend test suite was run for this report.

## 8. What is implemented, and what is not

| Area | Status |
|---|---|
| Complaint, incident, report link, work order | Implemented, with migrations |
| Tracking ID and public tracker | Implemented |
| Ten-stage LangGraph pipeline | Implemented |
| Idempotent create and one active work order under concurrent reports | Implemented and covered by tests |
| Officer confirm, reject, merge, and split | Implemented. Split is the unlink. There is no separate unlink button |
| SLA scan and escalation on the incident | Implemented |
| Dispute and reopen by a linked reporter after resolution | Implemented |
| Web, mobile, voice, and WhatsApp adapters | Written and tested. Not called by the live form or the graph |
| Live WhatsApp, helpline, or email intake | Not implemented |
| Photo understanding beyond a perceptual hash | Not implemented |
| Graph memory after a process restart | Not implemented. Database rows remain |
| Thresholds tuned on real officer decisions | Script exists and does not apply changes by itself. It was not run for this report |
| City-scale load test or security audit | Not done |

## 9. Stack actually used

Python, TypeScript, FastAPI, LangGraph, SQLAlchemy, Alembic, React 19, Vite, Tailwind CSS, Leaflet, SQLite for the demo, pytest, and ImageHash. Adapters for Groq, Gemini, and OpenAI exist. This run did not call them. A PostgreSQL driver is in the requirements and was not the database for these measurements.

## 10. How to see it

From the repository root in PowerShell:

```powershell
make run
```

Open `http://localhost:5173`. Demo sign-in is `citizen@demo.namma-civic.ai` with password `password123`. Submit a report, copy the tracking ID, and open Track.
