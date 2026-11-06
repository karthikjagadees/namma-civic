# Local run and home page polish

## Start the app on Windows

From the repository root in PowerShell, run:

```powershell
make run
```

The script starts the FastAPI backend and Vite frontend from the same PowerShell session. The web page opens at `http://localhost:5173`; FastAPI docs are at `http://localhost:8000/docs`. Press **Ctrl+C** in that PowerShell session to stop both services.

If either port already has a listener, the launcher reuses it and starts only the service on the free port. This supports the common case where the backend is already running in another PowerShell window.

The launcher selects an existing Python environment when available, defaults to mock AI/MCP/SMS/geocoding settings, and puts the SQLite demo database under `%TEMP%\namma-civic-live-demo`. The normal `make run` therefore does not need or use the project `.env` file for AI credentials.

For an explicitly requested live AI run, set the provider mode before launching. For example, after adding a valid `GROQ_API_KEY` and `GROQ_MODEL` to the project `.env`:

```powershell
$env:NAMMA_CIVIC_AI_MODE = 'groq'
make run
```

The launcher passes the project `.env` to Uvicorn only in live mode. A report then makes one Groq text-model request in the current intake path. Stop any existing backend first; the launcher refuses to silently reuse an already-running backend in live mode. Reset the opt-in after stopping:

```powershell
Remove-Item Env:NAMMA_CIVIC_AI_MODE
```

The Groq image-analysis adapter currently returns fixed synthetic image findings rather than sending an image to Groq. Keep the default mock mode for tests and deterministic demos. Live AI mode can incur provider usage and sends complaint text to Groq.

A `Makefile` includes a `run` target for systems with GNU Make:

```powershell
make run
```

GNU Make 4.4.1 is installed for this Windows user with `winget`. Open a new PowerShell window after installation so the updated PATH is loaded, then `make run` works as written. `.\run.ps1` remains available as the direct PowerShell alternative.

## What changed on the home page

The home page now describes the citizen flow with four aligned steps: submit a report, add details, follow updates, and officer review. Feature cards use consistent spacing and heights. Unverified marketing claims about agent count, provider branding, SLA percentages, and response speed were removed so the page describes capabilities that exist in the repository.

## Why this launcher shape

The project needs two long-running development servers. Separate PowerShell windows are possible, but they make cleanup less clear. This launcher runs both child processes from one terminal session, waits until both local URLs respond, opens the web app, and stops both child processes when the user presses Ctrl+C.

The Makefile is a thin wrapper around the PowerShell script. This keeps Windows setup in native PowerShell while still offering the familiar `make run` target where GNU Make is available.

## Evidence and limits

The frontend production build completed with Vite 8.3.6. The built JavaScript chunk is above Vite's 500 kB warning threshold; this change does not split the bundle.

The launcher smoke run returned HTTP 200 from the frontend and `online` from the backend root endpoint. Startup uses mock providers and a temporary SQLite database. No live LLM or notification provider is used.
