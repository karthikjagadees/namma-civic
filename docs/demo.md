# Namma Civic — Demo Scenario

## The Demo Story

A citizen walks by a large pothole near their college entrance. Vehicles are struggling to pass. They open Namma Civic on their phone.

---

## Step-by-Step Demo

### Step 1: Citizen Reports

The citizen opens the Report Issue page.

- **Input type:** Image + Text
- **Photo:** Pothole image
- **Description:** "Large pothole near the college entrance. Vehicles are having difficulty passing."
- **Location:** GPS auto-detected (lat: 22.57, lng: 88.36)

Clicks **Submit Report**.

---

### Step 2: AI Processing (Automated)

The UI shows: *"AI is analyzing your report..."*

Behind the scenes, the LangGraph graph executes:

```
✓ Intake Agent       — Parsed text, detected language: English
✓ Vision Agent       — Detected: pothole, severity estimate: 8/10
✓ Location Agent     — Address: MG Road, Kolkata | Jurisdiction: Zone 5
✓ Validation Agent   — Report valid, no issues
✓ Duplicate Agent    — Found 6 nearby reports within 300m
✓ Priority Agent     — Score: 0.87 → CRITICAL
   Reason: High safety risk + 6 duplicate reports + busy road
✓ Routing Agent      — Roads Department (confidence: 0.96)
✓ Action Agent       — Civic Task CF-1024 created
✓ Monitoring Agent   — SLA: 2 hours (CRITICAL priority)
```

---

### Step 3: Citizen Sees Result

```
Complaint ID: CF-1024

Category:     Road Damage / Pothole
Severity:     8/10
Priority:     🔴 CRITICAL

Department:   Roads Department
Response SLA: 2 hours

Why CRITICAL?
• Safety risk detected in image (severity 8/10)
• 6 nearby reports confirm widespread issue
• High-traffic road location

AI Agent Timeline:
✓ Intake Agent      0.2s
✓ Vision Agent      1.4s
✓ Location Agent    0.3s
✓ Validation Agent  0.1s
✓ Duplicate Agent   0.4s
✓ Priority Agent    0.2s
✓ Routing Agent     0.3s
✓ Action Agent      0.5s
✓ Monitoring Agent  0.1s
```

---

### Step 4: Officer Dashboard

Roads Department Officer receives notification:

> **New CRITICAL Task — CF-1024**
> Road Damage / Pothole — MG Road, Kolkata
> SLA: 2 hours | 6 related reports

Officer opens the task:

- Views AI analysis summary
- Views image on interactive map
- Clicks **Accept Task**
- Status → IN_PROGRESS

---

### Step 5: Resolution

Officer's team repairs the pothole. Officer uploads an **after photo**.

Namma Civic runs **Resolution Verification Agent**:

```
Before: Large pothole — road surface severely damaged
After:  Road resurfaced — pothole filled and repaired

Resolution Confidence: 94%
Status: AI VERIFIED ✓
```

---

### Step 6: Citizen Notified

Citizen receives notification:

> **Your complaint CF-1024 has been resolved!**
> AI verified resolution with 94% confidence.
> View before/after photos.

Citizen sees:

| Before | After |
|---|---|
| [pothole image] | [repaired road image] |

---

### Step 7: Analytics Updated

The admin analytics dashboard updates:

- Category trend: Road Damage +1
- Resolution time: 1h 45min (within SLA)
- Department KPI: Roads Dept. SLA compliance 96%
- Hotspot: MG Road cluster resolved

---

## Running the Demo

### Seed Data

```bash
cd backend
python database/seed/seed_demo.py
```

This creates:
- 3 demo users (citizen, officer, admin)
- 5 departments
- 100 complaints across categories
- Varied priorities, statuses, locations
- 15 resolved complaints with evidence
- 8 duplicate groups
- 3 active hotspots

### Demo Accounts

| Role | Email | Password |
|---|---|---|
| Citizen | citizen@demo.namma-civic.ai | demo1234 |
| Officer | officer@demo.namma-civic.ai | demo1234 |
| Admin | admin@demo.namma-civic.ai | demo1234 |
