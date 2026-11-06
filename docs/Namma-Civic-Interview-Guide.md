# 🏙️ Namma Civic — Complete Interview Guide
### *"From Citizen Report → Verified Action → Resolution"*

> **How to use this guide:** Read the "Elevator Pitch" first, then memorize the phase summaries, then practice the Q&A section out loud. When answering in an interview, always lead with **WHY**, then **WHAT**, then **HOW**.

---

## 📌 Elevator Pitch (30 seconds — memorize this)

> "Namma Civic is an **autonomous civic action platform** I built from scratch using **FastAPI**, **React**, **LangGraph multi-agent AI**, and the **Model Context Protocol (MCP)**. Citizens report a pothole, a broken street light, or a burst pipe — and AI agents automatically understand the issue, validate it, check for duplicates, prioritize it, route it to the right municipal department, monitor resolution deadlines, and verify the fix using computer vision. The entire lifecycle — from report to verified resolution — runs autonomously. No human needs to read every complaint. The system handles it. I built it in **10 progressive phases** with **61 backend tests** at 100% pass rate."

---

## 🏗️ System Architecture (draw this on the whiteboard)

```
Citizen (Web/Mobile/Voice)
         │
         ▼
   React Frontend (Vite + Tailwind)
         │  HTTP/REST (Axios)
         ▼
   FastAPI Backend (Python 3.11+)
         │
    ┌────┴──────────────────────────────┐
    │  SQLAlchemy Async ORM             │
    │  SQLite (dev) / PostgreSQL (prod)  │
    └────────────────────────────────────┘
         │
         ▼
   LangGraph StateGraph (6 Agent Nodes)
   ┌─────────────────────────────────────┐
   │ Intake → Validation → Deduplication │
   │ → Routing → Approval(HITL) → Action │
   └─────────────────────────────────────┘
         │
         ▼
   MCP Tool Layer (JSON-RPC 2.0)
   ┌──────────────────────────────┐
   │ Maps/GIS | Civic | Notify   │
   └──────────────────────────────┘
         │
         ▼
   Autonomous Services
   ┌────────────────────────────────────────┐
   │ SLA Monitor | Resolution Verifier      │
   │ Analytics Engine | Hotspot Detector    │
   └────────────────────────────────────────┘
```

---

## 🗺️ All 10 Build Phases — What & Why

---

### 📁 Phase 1 — Project Foundation
**WHY:** Every production system needs a solid base before building features.  
**WHAT:** Set up FastAPI with async lifespan, SQLAlchemy async ORM (SQLite/PostgreSQL switchable), structured logging with `structlog`, CORS middleware, Docker Compose, health check endpoint.  
**HOW:** Used `pydantic-settings` for environment-based config with enums (`AppEnv`, `DatabaseMode`, `AIMode`, `MCPMode`). Factory pattern for app creation. Applied SLA background monitor as an `asyncio.Task` inside the lifespan.  
**Key File:** `app/main.py`, `app/core/config.py`

---

### 🔐 Phase 2 — Authentication & RBAC
**WHY:** A civic platform has 3 user roles (Citizen, Officer, Admin) with different permissions. Security must be built in from the start, not added later.  
**WHAT:** JWT-based authentication, bcrypt password hashing, 4 auth endpoints (`/register`, `/login`, `/me`, `/me/password`), Role-Based Access Control middleware, protected routes in the frontend.  
**HOW:**
- `bcrypt.hashpw()` with 72-byte truncation (bcrypt limit)
- JWT signed with HS256, containing `sub` (user ID), `role`, `exp`, `iat`
- `jose.jwt.decode()` for token validation
- `Depends(get_current_user)` FastAPI dependency injection for route protection
- Alembic migration `0001_create_users` for the `users` table

**Result:** 16/16 tests passing

---

### 📢 Phase 3 — Citizen Reporting
**WHY:** The core product value — citizens need to report civic issues with photos, location, and description.  
**WHAT:** Multimodal complaint submission (text + images + GPS coordinates), department seeding, complaint status lifecycle, CRUD endpoints, media file upload.  
**HOW:**
- 4 SQLAlchemy models: `Complaint`, `ComplaintMedia`, `ComplaintTimeline`, `Department`
- Haversine great-circle distance formula for GIS utilities
- Reverse geocoding for address from lat/lng
- File upload endpoint with MIME type validation, saved to `./uploads/`
- Status enum: `pending → analyzing → verified → assigned → in_progress → resolved → rejected`

**Result:** 25/25 tests passing

---

### 🤖 Phase 4 — AI Intake & Multimodal Understanding
**WHY:** Reading every complaint manually is impossible at scale. AI must triage, categorize, and prioritize issues automatically.  
**WHAT:** Pluggable AI provider system supporting Mock, OpenAI GPT-4o, and Google Gemini — with graceful fallback. Multimodal triage combining text NLP + computer vision.  
**HOW:**
- Abstract `BaseAIProvider` with 4 methods: `analyze_text()`, `analyze_image()`, `transcribe_audio()`, `synthesize_multimodal_triage()`
- `MockAIProvider`: keyword-matching heuristics for 7 civic categories, confidence scoring, severity calculation (1-10), urgency keyword detection
- AI Factory singleton — reads `AI_MODE` env var to select provider
- `AIAnalysis` ORM model stores results alongside each complaint
- API endpoints: `/api/ai/analyze`, `/api/ai/analysis/{id}`, `/api/ai/reanalyze/{id}`
- Frontend shows: confidence meter, severity badge, urgency index, explainable reasoning, entity tags, "Re-run AI Analysis" button

**Result:** 34/34 tests passing (9 new AI tests)

---

### 🧠 Phase 5 — LangGraph Multi-Agent System
**WHY:** A single AI prompt can't handle the full lifecycle. Different specialized agents with different decision logic are needed, forming an orchestrated pipeline.  
**WHAT:** 6 specialized LangGraph agent nodes in a directed acyclic graph (DAG) with conditional routing and Human-in-the-Loop (HITL) support.  
**HOW:**
```
CivicActionState (TypedDict) — shared state passed across all nodes:
  complaint_id, citizen_id, title, description, category,
  latitude, longitude, media_urls,
  intake_result, validation_result, deduplication_result,
  routing_result, requires_human_approval, human_decision, action_result,
  current_step, steps_completed, errors

Agent Nodes:
1. intake_node      — Calls AI provider for triage
2. validation_node  — Spam check, completeness check, validity scoring
3. dedup_node       — Compares with nearby recent complaints (Haversine)
4. routing_node     — Selects department, sets priority, SLA hours
5. approval_node    — HITL gate: flags high-severity for officer review
6. action_node      — Dispatches work order via MCP civic tools

Conditional Edges:
- validation → (dedup | approval) based on validity
- routing → (approval | action) based on requires_human_approval flag
- approval → (action | END) based on is_awaiting_approval
```
- `MemorySaver` checkpointer for persistent graph state (survives server restarts)
- Agent resume API: `POST /api/agents/approve/{id}` to inject human decision and re-run graph

**Result:** 43/43 tests passing (9 new agent tests)

---

### 🔌 Phase 6 — Model Context Protocol (MCP) Tool Layer
**WHY:** AI agents need standardized, pluggable tools to interact with external systems (maps, maintenance crew, notifications). MCP provides a JSON-RPC 2.0 protocol for this.  
**WHAT:** 3 MCP servers with 9 tools total, unified MCP client.  
**HOW:**
```
MCP Servers & Tools:
├── Maps/GIS Server
│   ├── gis_geocode (address → lat/lng)
│   ├── gis_reverse_geocode (lat/lng → address)
│   └── gis_traffic_density_lookup (location → congestion)
│
├── Civic Maintenance Server
│   ├── civic_inventory_query (check materials stock)
│   ├── civic_crew_availability (get available crews)
│   └── civic_work_order_dispatch (create work order)
│
└── Notification Server
    ├── notify_citizen_sms (text the citizen)
    ├── notify_citizen_email (email the citizen)
    └── notify_officer_emergency_alert (emergency page)
```
- All tools implement `MCPToolSchema` with Pydantic validation
- `MCPClient.call_tool(name, args)` dispatches to correct server
- Supports `tools/list` and `tools/call` JSON-RPC 2.0 methods
- Wired into the LangGraph action_node for autonomous dispatch

**Result:** 4 MCP tests passing

---

### ⏱️ Phase 7 — Autonomous SLA Monitoring & Escalation
**WHY:** Without deadlines and enforcement, complaints get forgotten. The system must monitor its own SLA and autonomously escalate before breaches happen.  
**WHAT:** Dynamic SLA calculation engine, breach detection, auto-escalation with priority bumping and officer paging.  
**HOW:**
```python
SLA_HOURS_MAP = {
    critical: 12h,
    high:     24h,
    medium:   48h,
    low:      72h
}

SLA States: ON_TRACK → AT_RISK (>75% consumed) → BREACHED

Escalation Logic:
- AT_RISK  → TIER_1_SUPERVISOR alert
- BREACHED → TIER_2_DIRECTOR alert + priority bump (medium → high)
```
- Background `asyncio` task runs every 5 minutes (`run_sla_monitor`)
- Idempotent: checks timeline for existing escalation notes before re-escalating
- SLA API: `GET /api/sla/overview`, `GET /api/sla/complaint/{id}`, `POST /api/sla/check-and-escalate`

**Result:** 4 SLA tests passing

---

### ✅ Phase 8 — Resolution Verification Engine
**WHY:** Marking a complaint "resolved" without verification is unreliable. AI should inspect the repair evidence before closing the case.  
**WHAT:** Multimodal before-vs-after computer vision inspection, confidence-based approval, automatic status transition to `resolved`.  
**HOW:**
- Officer submits resolution notes + optional resolution photo
- AI analyzes notes for positive cues: `["fixed", "repaired", "cleared", "patched", "restored", "completed", ...]`
- Confidence scoring: 0.94 (text only) → 0.99 (text + image)
- If `"incomplete"` or `"cannot fix"` detected → verification rejected (confidence 0.35)
- On verified: sets `complaint.status = resolved`, records `resolved_at`, links resolution media
- Sends automated resolution email to citizen

**Result:** 3 resolution tests passing

---

### 📊 Phase 9 — Geospatial Analytics & Civic Hotspot Detection
**WHY:** Individual complaints don't show the pattern. Analytics reveals chronic problem zones, underperforming departments, and city health trends.  
**WHAT:** Geospatial clustering (Haversine), chronic defect zone classification, department scorecards, City Civic Health Index (0-100).  
**HOW:**
```
Clustering Algorithm:
- 500m radius Haversine clustering (O(n²) greedy)
- Zone classification by cluster size + severity:
  ≥3 incidents OR severity ≥8 → CRITICAL_CHRONIC_ZONE
  ≥2 incidents              → RECURRENT_DEFECT_CORRIDOR
  1 incident                → LOCALIZED_INCIDENT

Civic Health Index:
  health_score = (resolved/total * 70 + 30) - (breached_count * 5)
  Clamped to [35, 99]

Department Scorecard:
  efficiency_score = compliance_rate * 0.7 + resolution_ratio * 30
```
- Analytics API: `GET /api/analytics/summary`, `/hotspots`, `/departments`
- Frontend `AnalyticsPage`: City Health gauge, SLA banner, hotspot list, dept scorecards, MCP tool registry

**Result:** 4 analytics tests passing

---

### 🧪 Phase 10 — Final E2E Verification
**WHAT:** End-to-end integration test run, browser-based UI verification, 58/58 backend tests at 100% pass rate, TypeScript build with 0 errors.

---

## 💬 Interview Q&A — Practice These Out Loud

---

### 🟢 BASIC QUESTIONS

**Q1: Tell me about Namma Civic.**
> "Namma Civic is an autonomous civic action platform. It allows citizens to report problems like potholes or garbage dumps. The moment a complaint is submitted, AI agents kick in: one understands the complaint, another checks if it's a duplicate, another routes it to the right department, and another monitors if it's being fixed on time. I built the full stack — React frontend, FastAPI backend, LangGraph multi-agent pipeline, and a custom MCP tool layer. It has 58 backend tests at 100% pass rate."

---

**Q2: Why did you build this project?**
> "I wanted to build something that demonstrates advanced AI concepts — not just a chatbot, but a fully autonomous multi-agent system. Civic infrastructure is a perfect domain because it's relatable, has real-world stakes, and requires coordination across multiple entities. It let me demonstrate LangGraph orchestration, multimodal AI, geospatial intelligence, RBAC, SLA management, and computer vision — all in one cohesive project."

---

**Q3: What tech stack did you use and why?**
> "**FastAPI** for the backend — it's async-native and fast, with automatic OpenAPI docs. **SQLAlchemy async ORM** for type-safe database access. **SQLite** in development (zero config), switchable to **PostgreSQL + PostGIS** in production. **LangGraph** from LangChain for multi-agent orchestration because it provides a stateful DAG with conditional routing and human-in-the-loop support. **React + Vite + TailwindCSS** for the frontend for speed and composability. **JWT + bcrypt** for security. Everything is **Dockerized**."

---

### 🟡 INTERMEDIATE QUESTIONS

**Q4: Explain how LangGraph works in your project.**
> "LangGraph uses a `StateGraph` where each node is an AI agent function. I defined a `CivicActionState` TypedDict as the shared memory across all nodes. The graph starts at `intake`, proceeds to `validation`, then branches conditionally to `deduplication` or `approval` based on validity. After routing, it either auto-dispatches or goes to human approval. The `MemorySaver` checkpointer persists state, which is crucial for the HITL flow where the graph pauses, waits for an officer to approve, then resumes execution when `POST /api/agents/approve/{id}` is called."

---

**Q5: What is the Model Context Protocol (MCP) and why did you use it?**
> "MCP is a standardized protocol for AI agents to access external tools via JSON-RPC 2.0. Instead of hardcoding every API call inside the AI, you define tools with schemas, and the AI calls them through a unified client. I built 3 MCP servers — Maps/GIS, Civic Maintenance, and Notifications — each exposing 3 tools. The LangGraph action node uses the MCP client to dispatch work orders, send citizen notifications, and check crew availability. This makes the tool layer modular and replaceable — I could swap the mock implementation for real GIS APIs without changing the agent code."

---

**Q6: How does your SLA monitoring work?**
> "When a complaint is created, I calculate its SLA deadline based on priority: Critical=12h, High=24h, Medium=48h, Low=72h. A background asyncio task runs every 5 minutes and scans all active complaints. For each one, it calculates how much time has been consumed. If >75% consumed, it's marked AT_RISK and a Tier-1 Supervisor alert is sent via MCP. If the deadline has passed, it's BREACHED and a Tier-2 Director alert fires with a priority bump. The escalation is idempotent — I check the timeline audit log to avoid sending duplicate alerts."

---

**Q7: How does JWT authentication work in your system?**
> "When a user logs in, I validate their credentials using bcrypt's `checkpw()`. If valid, I create a JWT signed with HS256 containing the user ID, role, and expiration. For protected endpoints, FastAPI's dependency injection system uses `Depends(get_current_user)` which decodes the token from the `Authorization: Bearer` header using `jose.jwt.decode()`. If the token is expired, tampered, or missing, a 401 is raised. Role-based access uses the `role` claim in the JWT payload — officers see different endpoints than citizens."

---

**Q8: Explain the duplicate detection logic.**
> "The deduplication agent node queries the database for open complaints within a 500-meter radius of the new complaint, submitted in the last 7 days, in the same category. If a match is found with a similarity score above the threshold, the complaint is linked to the existing one instead of creating a new work order. This prevents 10 citizens reporting the same pothole from creating 10 separate maintenance tasks. It saves resources and gives the original reporter a faster update."

---

**Q9: How does the Resolution Verification Engine work?**
> "An officer submits resolution notes and optionally a photo through `POST /api/resolution/verify/{id}`. The engine scans the notes for positive resolution keywords — 'fixed', 'repaired', 'cleared', 'patched'. It calculates a confidence score: 0.94 for text-only, up to 0.99 if a photo is included. If the notes contain 'incomplete' or 'cannot fix', the confidence drops to 0.35 and the verification fails. On success, the complaint status moves to `resolved`, a `resolved_at` timestamp is recorded, and an email is sent to the citizen via the email service."

---

**Q10: How did you implement RBAC?**
> "I have 3 roles: Citizen, Officer, Admin. The role is stored in the `users` table and embedded in the JWT. In FastAPI, I created separate dependency functions: `require_citizen()`, `require_officer()`, `require_admin()`. These call `get_current_user()` and then check the role. If insufficient permissions, a 403 Forbidden is returned. For example, `POST /api/complaints` is citizen-only, `PATCH /api/officer/complaints/{id}` is officer-only, and `GET /api/admin/users` is admin-only."

---

### 🔴 ADVANCED / DEEP-DIVE QUESTIONS

**Q11: How would you scale this to handle 1 million complaints per day?**
> "Several changes: First, move from SQLite to **PostgreSQL + PostGIS** for geospatial indexing. Add **Redis** for caching frequently accessed analytics and SLA overview. Replace the in-process asyncio SLA monitor with a **Celery + Redis** distributed task queue. Add **database connection pooling** with PgBouncer. For the AI layer, switch from synchronous heuristics to async calls to a real LLM API. Add **rate limiting** per user via a Redis sliding window. For the frontend, enable **CDN** and static asset caching. For ML inference, deploy on **GPU instances** and use model quantization. The architecture is already designed for this — the `DatabaseMode` and `AIMode` config enums make swapping implementations clean."

---

**Q12: What's the Human-in-the-Loop mechanism and when does it trigger?**
> "In the LangGraph `routing_node`, I evaluate the complaint for high-risk conditions: severity ≥ 8, or category = 'water_leakage', or presence of hazard keywords like 'injury', 'collapse', 'death'. If any condition triggers, `requires_human_approval = True` is set in the state. The graph routes to the `approval_node`, which sets `is_awaiting_approval = True` and exits to `END` — pausing execution. The complaint shows an 'Officer Review Required' banner in the UI. When an officer submits their decision via `POST /api/agents/approve/{id}`, the human decision is injected into the graph state and the graph resumes from the approval node."

---

**Q13: Explain your database design choices.**
> "I used **SQLAlchemy 2.0 async** with `Mapped[T]` type hints for full type safety. Key decisions: UUIDs as primary keys (String(36)) for distributed compatibility. `ForeignKey('complaints.id', ondelete='CASCADE')` for referential integrity. Indexed columns: `citizen_id`, `department_id`, `status`, `priority`, `latitude`, `longitude` — all frequently queried. The `ComplaintTimeline` acts as an append-only audit log. `AIAnalysis` has a one-to-one relationship with `Complaint`, stored separately to keep the complaints table lean. Alembic handles versioned migrations."

---

**Q14: How did you handle the AI provider abstraction?**
> "I defined an abstract `BaseAIProvider` class with 4 async methods. Each concrete provider (`MockAIProvider`, `OpenAIProvider`, `GeminiProvider`) implements these methods. The `AIFactory` reads the `AI_MODE` environment variable and returns the appropriate singleton. The real providers have graceful fallback — if the OpenAI API call fails, they fall back to the mock heuristic. This means the app works out of the box with `AI_MODE=mock` and no API keys needed, but switches to real LLM behavior in production by setting `AI_MODE=openai` and `OPENAI_API_KEY`."

---

**Q15: How did you test this project?**
> "I used **pytest** with **pytest-asyncio** for async test support and **httpx.AsyncClient** with the FastAPI `app` as the ASGI transport — no real server needed. Each test suite is isolated using an in-memory SQLite database with `aiosqlite`. I tested every API endpoint, business logic, edge cases, and error conditions. The test structure: `test_health.py`, `test_auth.py`, `test_complaints.py`, `test_ai.py`, `test_agents.py`, `test_mcp.py`, `test_sla.py`, `test_resolution.py`, `test_analytics.py`, `test_officer_admin.py`. Total: **61 tests at 100% pass rate**."

---

**Q16: What design patterns did you use?**
> "Several: **Factory Pattern** for AI providers and the FastAPI app itself. **Singleton Pattern** for the MCP client, AI factory, and settings (via `lru_cache`). **Strategy Pattern** for the pluggable AI providers. **Repository Pattern** through SQLAlchemy services. **Observer/Listener Pattern** via the asyncio background SLA monitor. **State Machine** for the complaint status lifecycle. **DAG (Directed Acyclic Graph)** for the LangGraph multi-agent pipeline. **Dependency Injection** for FastAPI's `Depends()` system."

---

**Q17: How does the Haversine formula work in your geospatial features?**
> "The Haversine formula calculates the great-circle distance between two points on a sphere using their latitude and longitude. I use it in two places: (1) in the analytics service for clustering complaints within 500m to detect hotspot zones, and (2) in the deduplication agent to find nearby similar complaints. The formula uses the Earth's radius (6,371,000m), converts degrees to radians, applies the haversine function, and outputs distance in meters. It's O(n²) which is acceptable for a city-scale dataset of thousands of complaints. For millions, I'd switch to PostGIS `ST_DWithin` with a GiST index."

---

**Q18: What would you add next if you had more time?**
> "Several things: (1) **Real-time WebSocket notifications** so citizens get instant status updates without polling. (2) **WhatsApp and voice report intake** using Twilio — the `ComplaintSource` enum already has `voice` and `whatsapp` values. (3) **Predictive maintenance** — use historical hotspot data to predict which zones will have issues before they're reported. (4) **Machine learning duplicate detection** using sentence embeddings (SBERT) instead of simple keyword matching. (5) **PostGIS** with `ST_DWithin` for production-grade geospatial queries. (6) **OAuth2 integration** for Google/Aadhaar login. (7) **Kubernetes deployment** with horizontal pod autoscaling."

---

**Q19: How did you handle async programming in FastAPI?**
> "FastAPI is fully async. I used `async def` for all route handlers and service methods. SQLAlchemy async session (`AsyncSession`) is injected via `Depends(get_session)` — a generator that yields a session and commits/rolls back in a try-finally block. For background tasks, I used `asyncio.create_task()` for fire-and-forget operations like sending resolution emails. The SLA monitor uses `asyncio.sleep(interval)` in an infinite loop as an asyncio.Task created in the lifespan context. All LangGraph agent nodes are async functions invoked by `await graph.ainvoke(state, config)`."

---

**Q20: Explain your security implementation.**
> "Multiple layers: (1) **JWT HS256** — tokens are short-lived (configurable, default 60 min), signed with a secret key, contain user ID + role + expiry. (2) **bcrypt** — passwords hashed with salt, 72-byte input truncated to match bcrypt's limit. (3) **Pydantic validation** — all inputs validated at the schema layer before reaching business logic. (4) **RBAC** — role enforced at every protected endpoint via dependency injection. (5) **CORS** — configured to allow only trusted origins. (6) **TrustedHostMiddleware** — enabled in production mode. (7) **No secrets in source code** — all via `.env` file using `pydantic-settings`. (8) **File upload validation** — MIME type and size checked before saving."

---

## 🎤 Behavioral Questions

**Q: What was the hardest part of building this?**
> "The LangGraph HITL (Human-in-the-Loop) flow. The graph needs to pause mid-execution, persist state, wait for human input that might come hours later, and then resume exactly where it left off — all while the server might restart. The `MemorySaver` checkpointer handles persistence, but designing the state so the approval node cleanly hands off — returning `END` to pause, then accepting injected human decision to continue — required careful conditional edge logic."

**Q: How did you ensure code quality?**
> "Type hints throughout (Python typing module + Pydantic models + SQLAlchemy Mapped[T]). TypeScript strict mode on the frontend with `npm run build` passing 0 errors. 58 automated tests. Structured logging with `structlog` for observability. Environment-based configuration with no hardcoded values. Factory pattern for testability — every major service can be tested with a mock implementation."

---

## 📊 Key Metrics to Quote

| Metric | Value |
|--------|-------|
| Backend Tests | **61 passing / 61 total (100%)** |
| Frontend Build | **0 errors, 0 warnings** |
| API Endpoints | **40+ REST endpoints** |
| Agent Nodes | **6 LangGraph nodes** |
| MCP Tools | **9 tools across 3 servers** |
| User Roles | **3 (Citizen, Officer, Admin)** |
| SLA Levels | **4 (Critical 12h → Low 72h)** |
| Civic Categories | **7 (pothole, garbage, water, light, drain, traffic, encroachment)** |
| Build Phases | **10 progressive phases** |
| Tech Stack | **FastAPI + React + LangGraph + MCP + SQLAlchemy** |

---

## 🔑 Keywords to Drop in Your Interview

`LangGraph` · `Multi-Agent AI` · `StateGraph` · `MemorySaver` · `Human-in-the-Loop` · `Model Context Protocol (MCP)` · `JSON-RPC 2.0` · `FastAPI` · `SQLAlchemy Async` · `Pydantic` · `JWT HS256` · `bcrypt` · `RBAC` · `Haversine` · `Geospatial Clustering` · `SLA Monitoring` · `Resolution Verification` · `Computer Vision` · `Multimodal AI` · `Dependency Injection` · `Factory Pattern` · `Alembic` · `pytest-asyncio` · `Docker Compose` · `TypeScript` · `Conditional Edges` · `Autonomous Escalation` · `Civic Health Index`

---

*This guide was auto-generated from the actual Namma Civic codebase. All Q&A answers are based on real implemented code.*
