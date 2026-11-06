# 🚀 Deploying Namma Civic to Vercel (Frontend & Backend)

Namma Civic is fully configured for deployment on [Vercel](https://vercel.com). Both the **React + Vite frontend** and the **FastAPI Python backend** can be deployed either together in a single Vercel project or as two separate linked Vercel projects.

---

## 🏗️ Architecture on Vercel

```
[ Citizen / Browser ]
        │
        ▼
   https://your-namma-civic.vercel.app
        ├── /api/*   ──────► Python Serverless Function (FastAPI, backend/api/index.py)
        │                     ├── SQLite in /tmp (Demo mode with auto-seeding)
        │                     └── Or PostgreSQL + PostGIS (Production: Supabase / Neon)
        └── /*       ──────► Vite Single-Page Application (HTML, JS, CSS, Leaflet, GSAP)
```

---

## ⚡ Method 1: Two Vercel Projects (Recommended)

Deploying Frontend and Backend as two separate projects in Vercel is the most flexible and standard approach for full-stack apps.

### Step 1: Deploy Backend

1. Push your repository to **GitHub**.
2. Go to [vercel.com/new](https://vercel.com/new) and import your repository.
3. In **Project Settings**:
   - **Project Name**: `namma-civic-api`
   - **Framework Preset**: `Other`
   - **Root Directory**: Click `Edit` and select `backend`
4. Under **Environment Variables**, add:
   | Variable | Value | Notes |
   |---|---|---|
   | `APP_ENV` | `production` | Production mode |
   | `DEBUG` | `false` | Disable debug logs |
   | `AI_MODE` | `mock` | Or `openai` / `gemini` |
   | `DATABASE_MODE` | `sqlite` | Or `postgresql` |
   | `DATABASE_URL` | `sqlite:///./namma-civic.db` | Auto-routed to `/tmp/namma-civic.db` |
   | `AUTO_SEED` | `true` | Seeds demo accounts and departments |
   | `JWT_SECRET` | `generate-a-random-32-char-secret-key` | Token signing secret |
   | `CORS_ORIGINS` | `*` | Or your frontend URL |
5. Click **Deploy**.
6. Note down your backend URL (e.g., `https://namma-civic-api.vercel.app`).
7. Test the health endpoint: `https://namma-civic-api.vercel.app/api/health`

---

### Step 2: Deploy Frontend

1. Go to [vercel.com/new](https://vercel.com/new) and import the **same repository** again.
2. In **Project Settings**:
   - **Project Name**: `namma-civic-web`
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click `Edit` and select `frontend`
3. Under **Environment Variables**, add:
   | Variable | Value | Notes |
   |---|---|---|
   | `VITE_API_BASE_URL` | `https://namma-civic-api.vercel.app/api` | Point to your backend from Step 1; the frontend also adds `/api` if omitted |
4. Click **Deploy**.
5. Once deployed, open your frontend URL!

---

## ⚡ Method 2: Single Monorepo Vercel Project

The repository includes a root [vercel.json](../vercel.json) that compiles both frontend and backend together under one domain.

1. Go to [vercel.com/new](https://vercel.com/new) and import your repository.
2. Leave **Root Directory** as `./` (the root).
3. Under **Environment Variables**, add:
   | Variable | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `DEBUG` | `false` |
   | `AI_MODE` | `mock` |
   | `DATABASE_MODE` | `sqlite` |
   | `AUTO_SEED` | `true` |
   | `JWT_SECRET` | `your-secret-key` |
4. Click **Deploy**.
5. Vercel routes `/api/*` to the Python serverless function and all other routes to the Vite single-page application.

---

## 💻 Method 3: Deploy via Vercel CLI

Since you already have Vercel CLI installed:

```bash
# 1. Log in to your Vercel account
vercel login

# 2. Deploy Backend
cd backend
vercel --prod

# 3. Deploy Frontend (set VITE_API_BASE_URL to your backend URL)
cd ../frontend
vercel --prod
```

---

## 🔑 Demo Login Credentials (Auto-seeded)

When deployed with `AUTO_SEED=true` or in demo mode:

| Role | Email | Password |
|---|---|---|
| **Citizen** | `citizen@demo.namma-civic.ai` | `password123` |
| **Civic Officer (Roads)** | `roads.officer@demo.namma-civic.ai` | `password123` |
| **Civic Officer (Sanitation)** | `sanitation.officer@demo.namma-civic.ai` | `password123` |
| **Administrator** | `admin@demo.namma-civic.ai` | `password123` |

---

## 🗄️ Production Database (PostgreSQL + PostGIS)

For persistent data beyond ephemeral serverless containers, connect a cloud PostgreSQL database:

1. Create a free database on **Neon** ([neon.tech](https://neon.tech)) or **Supabase** ([supabase.com](https://supabase.com)).
2. Set environment variables on Vercel:
   ```env
   DATABASE_MODE=postgresql
   DATABASE_URL=postgresql+psycopg://username:password@your-db-host.neon.tech/namma-civic?sslmode=require
   ```
3. Enable PostGIS (optional for advanced GIS queries):
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

---

## 🤖 Real AI Providers (Optional)

To enable live OpenAI or Google Gemini AI models instead of heuristic mock mode:

```env
AI_MODE=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```
Or:
```env
AI_MODE=gemini
GOOGLE_API_KEY=AIza...
GOOGLE_MODEL=gemini-1.5-pro
```

---

## ✅ Deployment Checklist

- [x] Backend serverless entry point `backend/api/index.py` created
- [x] Backend `backend/vercel.json` configured for `@vercel/python`
- [x] Frontend `frontend/vercel.json` configured with SPA rewrites
- [x] Root `vercel.json` configured for unified monorepo deployment
- [x] Frontend `api.ts` normalizes `VITE_API_BASE_URL` to include `/api`, with same-origin fallback
- [x] Vercel serverless `/tmp` SQLite write handling configured
- [x] Auto-seed support enabled for zero-config demo experience
- [x] Serverless-safe background task skipping in `main.py`
- [x] `.vercel/` added to `.gitignore`
- [x] All 61 automated tests verified passing
