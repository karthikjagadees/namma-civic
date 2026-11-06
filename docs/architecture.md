# Namma Civic — System Architecture

## Overview

Namma Civic is a **closed-loop autonomous civic action platform**. A citizen submits a report; the system handles everything from understanding to resolution verification — autonomously.

```
Citizen Report (Text / Image / Voice)
          │
          ▼
    FastAPI Backend ─────────── JWT Auth / RBAC
          │
          ▼
   LangGraph Supervisor ◄──── Namma CivicState (typed dict)
    │
    ├── Intake Agent          ← parses raw input, calls AI
    ├── Vision Agent          ← analyses uploaded image
    ├── Location Agent        ← geocoding + jurisdiction
    ├── Validation Agent      ← validates completeness
    ├── Duplicate Agent       ← finds nearby similar reports
    ├── Priority Agent        ← calculates explainable score
    ├── Routing Agent         ← selects responsible dept
    ├── Action Agent          ← creates civic task via MCP
    ├── Monitoring Agent      ← SLA tracking + escalation
    └── Resolution Agent      ← verifies before/after images
          │
          ▼
     MCP Tool Layer
  ┌───────────────────────┐
  │  Maps / GIS Server    │  ← geocoding, nearby search, hotspots
  │  Civic DB Server      │  ← task CRUD, dept lookup
  │  Notification Server  │  ← email, SMS, in-app
  │  Policy Server        │  ← SLA rules, routing rules
  │  Analytics Server     │  ← statistics, trends
  └───────────────────────┘
          │
          ▼
    Database Layer
  ┌─────────────────────────────┐
  │  SQLite (development)       │
  │  PostgreSQL + PostGIS (prod)│
  └─────────────────────────────┘
          │
          ▼
    React Frontend (Vite + Tailwind)
  ┌──────────────────────────────────┐
  │  Landing Page                    │
  │  Citizen Portal                  │
  │  Civic Officer Dashboard         │
  │  Admin Panel                     │
  │  Interactive Map (Leaflet)       │
  │  Analytics (Recharts)            │
  └──────────────────────────────────┘
```

## Component Layers

### 1. API Layer (FastAPI)

- REST API with versioning (`/api/v1/...`)
- JWT-based authentication
- Role-based access control (citizen / officer / admin)
- Async request handling
- Pydantic v2 input/output validation
- Rate limiting

### 2. Orchestration Layer (LangGraph)

- `Namma CivicState` — typed shared state passed between agents
- Supervisor graph controls agent execution order
- Conditional edges based on state values
- Human-in-the-loop gates for critical decisions
- Agent retry with exponential backoff

### 3. Tool Layer (MCP)

- LangGraph agents call MCP tools, not raw functions
- Each MCP server is a separate service
- Mock mode for local development
- Standard MCP protocol for easy extension

### 4. Persistence Layer

- SQLAlchemy 2.x async ORM
- Alembic migrations
- SQLite in development (zero-config)
- PostgreSQL + PostGIS in production

### 5. Background Workers

- Celery tasks for SLA monitoring
- Redis as broker
- Periodic escalation checks

## Data Flow — Complaint Lifecycle

```
1. Citizen submits (POST /api/complaints)
2. FastAPI stores initial record (status=PENDING)
3. LangGraph graph triggered asynchronously
4. Intake Agent: parse text, detect language
5. Vision Agent: analyse image (if provided)
6. Location Agent: geocode address
7. Validation Agent: check completeness
8. Duplicate Agent: search nearby reports
9. Priority Agent: score + explain
10. Routing Agent: select department
11. Human Gate: if confidence < 0.70 or critical
12. Action Agent: create CivicTask via MCP Civic Server
13. Monitoring Agent: set SLA, begin watching
14. Officer accepts → updates status
15. Officer uploads resolution image
16. Resolution Agent: compare before/after via AI
17. Status → RESOLVED or HUMAN_REVIEW
18. Notification Agent: notify citizen
19. Analytics updated
```

## Security Architecture

- Passwords hashed with bcrypt
- JWT tokens (HS256, configurable expiry)
- RBAC enforced at router level via `Depends(require_role(...))`
- File uploads validated (type, size, content)
- CORS restricted to allowed origins
- All secrets via environment variables
- Audit log for every state-changing operation
