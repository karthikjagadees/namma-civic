# Namma Civic (Namma Civic)

Namma Civic is a civic-reporting **software prototype** built with FastAPI, SQLAlchemy, Alembic, LangGraph, and React/Vite. It groups likely duplicate reports into incidents while retaining each citizen's original report. Local tests and the demo use deterministic mock AI and simulated delivery/dispatch; the repository does not demonstrate a live municipal deployment.

## What is implemented

- Authenticated complaint submission and role/ownership checks on private report APIs.
- SQL-backed complaints, media metadata, incidents, versioned report-to-incident links, work orders, timelines, reporter preferences, notifications, and officer duplicate-review decisions.
- Alembic schema history in `backend/migrations/versions/`.
- A ten-node LangGraph workflow: intake, vision, validation, deduplication, routing, priority, approval, action, monitoring, and resolution verification. Several nodes are orchestration wrappers around deterministic logic or existing services, not separate AI models.
- Explainable duplicate scoring using spatial candidates and text, category, time, place, and image pHash signals. Outcomes are auto-link, officer review, or new incident.
- A report-only threshold recalibration script based on recorded officer decisions.
- Mockable MCP-style in-process tool adapters. No standalone `mcp-servers/` directory is present.

See the [learning guide](docs/learn/README.md) for the architecture and walkthroughs. See the [final requirement traceability](docs/learn/requirements-traceability.md) for met and open items.

## Technology and repository map

```text
backend/app/agents/       LangGraph state, graph, and nodes
backend/app/api/          FastAPI routes
backend/app/channels/     Canonical channel payloads and adapters
backend/app/deduplication/ Candidate retrieval, scoring, and evaluation
backend/app/models/       SQLAlchemy records
backend/app/services/     Application services
backend/app/mcp/          In-process tool registry and adapters
backend/app/workers/      Scheduled SLA monitor
backend/migrations/       Alembic configuration and schema revisions
backend/scripts/          Demo and evaluation/recalibration commands
backend/tests/            Offline backend tests
frontend/src/             React/Vite application
docs/learn/               Phase guides, handoff, and viva materials
```

## Run locally on Windows PowerShell

From the repository root, run both services with one command:

```powershell
make run
```

This starts both services in the current PowerShell window, uses the mock AI/MCP providers, and stores demo data in a temporary SQLite database. Open `http://localhost:5173` for the web app or `http://localhost:8000/docs` for the API. Press Ctrl+C in the PowerShell window to stop both services. GNU Make 4.4.1 is installed for this Windows user; reopen PowerShell after installing it so PATH refreshes. The equivalent direct PowerShell command is .\run.ps1.

If you prefer manual setup or need to install dependencies first, use the steps below.

Use the repository's existing virtual environment if you already have one. Otherwise, from the repository root:

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location backend
$env:AI_MODE = "mock"
$env:AI_PROVIDER = "mock"
$env:MCP_MODE = "mock"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

The API is at `http://localhost:8000`; Swagger UI is at `http://localhost:8000/docs`. Local development startup may seed demo records. Demo credentials are documented in `docs/learn/00-system-map.md`; use them only for local development.

Run the React app in another PowerShell window from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite prints the local frontend address when it starts.

## Offline verification

From `backend/`, with the active Python environment:

```powershell
$env:AI_MODE = "mock"
$env:AI_PROVIDER = "mock"
$env:MCP_MODE = "mock"
python -m pytest -q
python scripts\run_phase7_demo.py
```

The demo creates a temporary seeded SQLite database and runs a **synthetic** five-report scenario. Its MCP calls are replaced with deterministic local fakes. No live LLM, SMS, email, or dispatch call is required.

For duplicate threshold evaluation, run `python scripts\evaluate_duplicate_detection.py`. It generates and evaluates a labeled **synthetic** dataset; its numbers are not production accuracy results. See [the evaluation and limits](docs/learn/03-duplicate-detection.md).

## AI providers and external services

The backend includes mock, Groq, Gemini, and OpenAI provider adapters. Keep the mock provider configured for tests and demos. Selecting a live provider with usable credentials can make external model calls; do not do so without first agreeing on the expected call count. The mock configuration is deterministic for the test suite.

The MCP-style tools are registered and executed by in-process Python handlers, not separate MCP server processes. The SMS handler returns a synthetic delivery result; the civic dispatch handler returns a synthetic work-order ID. The email handler calls `EmailService`, which can use SMTP if configured, so a non-test run with SMTP credentials can send a real email. Automated tests use isolated settings, and the Phase 7 demo replaces tool calls with local fakes. The repository does not prove that an actual city department receives or acts on a dispatched work order.

## Safety and privacy boundaries

Citizen complaint lists are scoped to the authenticated citizen; officers/admins can inspect broader records. Public incident tracking omits reporter contact data and private report text. Complaint title, description, and category cannot be edited after submission through the update API. Image upload validates MIME, size, and readable image content.

These are application controls, not a substitute for an independent security review. No active rate-limiting middleware is wired in the current FastAPI application despite a rate-limit setting in configuration.

## Limitations

- The duplicate thresholds are calibrated on a small **synthetic** set and need evaluation on representative, consented local reports and officer labels.
- Text n-grams can miss paraphrases; pHash can confuse visually similar scenes and cannot recognize what an image depicts. Missing or inaccurate locations can make duplicate decisions uncertain.
- External channel connectors, production notification delivery, and municipal dispatch integration are not demonstrated here.
- LangGraph uses in-memory `MemorySaver`. A restart loses paused graph checkpoints, while committed SQL records remain.
- The global database serialization lock is correctness-oriented prototype logic; production concurrency and throughput are not verified.
- SLA and resolution verification are service-level heuristics and need operational policy validation.
- Image readability checks do not amount to malware scanning or complete validation of every media type.
- The project has not been independently security audited or tested at the stated “thousands of complaints” scale.

## Documentation

- [Learning guide and architecture story](docs/learn/README.md)
- [Phase 0 system map](docs/learn/00-system-map.md)
- [Data model](docs/learn/01-data-model.md)
- [Channels](docs/learn/02-channels.md)
- [Duplicate detection and synthetic evaluation](docs/learn/03-duplicate-detection.md)
- [Agent pipeline](docs/learn/04-agent-pipeline.md)
- [Follow-up](docs/learn/05-follow-up.md)
- [Officer review](docs/learn/06-officer-review.md)
- [End-to-end verification](docs/learn/07-verification.md)
- [Viva questions](docs/learn/viva-questions.md)
- [Local run and UI](docs/learn/08-local-run-and-ui.md)
- [Glossary](docs/learn/glossary.md)
- [Short demo script](docs/learn/demo-script.md)
- [Final requirement traceability](docs/learn/requirements-traceability.md)
