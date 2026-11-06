# Namma Civic demo script (about 4 minutes)

## Before the demo

Open PowerShell in `backend/`. Use the repository's Python environment and set mock modes for this terminal:

```powershell
$env:AI_MODE = "mock"
$env:AI_PROVIDER = "mock"
$env:MCP_MODE = "mock"
```

The scenario is synthetic. Its test replaces notification and dispatch calls with local fakes, so it does not contact citizens or a municipal system.

## 0:00–0:40 — State the problem

**Say:** “A city may receive multiple reports about the same issue. We must keep every citizen's original evidence, but staff should be able to work one shared incident and avoid duplicate work orders. This project is a prototype, so I'll distinguish simulated external operations from real database behavior.”

Point to `Complaint`, `Incident`, `ReportLink`, and `WorkOrder` in [the data-model guide](01-data-model.md). Explain that a report is evidence; the incident is the shared operational issue.

## 0:40–1:30 — Explain the decision flow

Open [duplicate detection](03-duplicate-detection.md). Walk through candidate retrieval, signal scoring, then the three outcomes: auto-link, officer review, or new incident. Explain that pHash compares visual patterns, while token and character n-gram scores compare text patterns. Neither understands the civic scene like a person.

**Say:** “If the report could bridge two existing incidents or the photo conflicts strongly, we route it to an officer. A likely match to a resolved incident creates a recurrence incident that points back to the old one.”

## 1:30–2:45 — Run the synthetic scenario

Run:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\run_phase7_demo.py
```

Show the output line labeled `dataset_kind: synthetic`. Explain the reported counts: source reports preserved, channel count, shared incident count, work-order count, and reporters with delivery records. State that the delivery results are local test records, not actual SMS/email messages.

## 2:45–3:30 — Explain human review and follow-up

Open [officer review](06-officer-review.md) and [follow-up](05-follow-up.md). Show how the officer decision preserves link history, how incident status and timeline are exposed without other reporters' personal data, and how notification preferences affect channels.

**Say:** “The graph can pause for a human decision. The pause is checkpointed in memory today, which means a process restart loses the paused graph state. The committed complaint and incident records remain in SQL.”

## 3:30–4:00 — State limitations and invite questions

**Say:** “The duplicate thresholds are from a small synthetic evaluation. They are not a real-city performance claim. The next evidence needed is labeled local reports, privacy review, production dispatch integration, and load/security testing.”

Invite the audience to ask what could create a false merge, why reports are not deleted, or how officer labels can inform threshold review.
