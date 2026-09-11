# LocalLift — Local SEO, Rankings & Reputation Operating System

> **Local SEO, Rankings & Reputation SaaS Operating System**

LocalLift is an enterprise-grade Local SEO management and automation SaaS platform built for local businesses, franchises, and marketing agencies.

---

## Quick Start (Single Terminal Command)

Start both **Frontend** and **Backend** simultaneously from the project root:

```bash
npm run dev
```

### Terminal Output Preview

```text
╔══════════════════════════════════════════════╗
║          LocalLift Development               ║
╚══════════════════════════════════════════════╝

Starting services...

[FRONTEND] Starting Vite Dev Server...
[BACKEND]  Starting FastAPI Uvicorn Server...

[FRONTEND] ✓ Running at http://localhost:5173
[BACKEND]  ✓ Running at http://localhost:8000 (API Docs: http://localhost:8000/docs)

✓ LocalLift development environment ready
```

---

## Service URLs

| Service | Local URL | Description |
| :--- | :--- | :--- |
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | React 18 + TypeScript + Vite Dashboard |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI REST API |
| **API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI Documentation |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Backend status health check |

---

## Available Development & Test Commands

Run from the root directory:

- `npm run dev`: Starts **both** Frontend and Backend concurrently with prefixed logs.
- `npm run dev:frontend`: Starts **only** the frontend Vite development server.
- `npm run dev:backend`: Starts **only** the backend FastAPI server.
- `npm test --prefix frontend`: Executes frontend Vitest test suite.
- `npm run build --prefix frontend`: Compiles TypeScript and builds the frontend production bundle.

---

## Testing & Quality Assurance

### Frontend Tests & Type Checking
```bash
# In frontend/ directory:
npm test            # Runs Vitest unit & regression suites
npm run build       # Compiles TypeScript and builds Vite bundle
```

### Backend Automated Test Suites
```bash
# In backend/ directory:
python test_data_integrity.py
python test_production_cleanliness.py
python test_category_system.py
python test_connections_and_auth_hardening.py
python test_team_and_my_projects.py
python test_schema_intelligence.py
python test_geogrid_location_fixes.py
python test_ai_and_final_verification.py
```

---

## Environment & Security Configuration

Copy `.env.example` to `.env` to configure your environment. **Never commit `.env` or production secrets to source control.**

```bash
cp .env.example .env
```

### Key Configuration Variables

| Variable | Default / Example | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Set to `production` in live deployments (enforces strict security). |
| `SECRET_KEY` | *(Set a 32+ char random string)* | JWT signing key. Mandatory in production mode. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./locallift.db` | Database connection string. Use PostgreSQL in production. |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins for authenticated API requests. |
| `SERP_PROVIDER` | `mock` or `serpapi` | Rank tracking provider (`serpapi` requires `SERPAPI_KEY`). |
| `AI_PROVIDER` | `rule_based` | AI engine (`gemini`, `openai`, or deterministic `rule_based`). |
| `GOOGLE_CLIENT_ID` | `...` | Google OAuth Client ID for GBP integration. |
| `GOOGLE_CLIENT_SECRET`| `...` | Google OAuth Client Secret. |

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts, Lucide Icons, Vitest.
- **Backend**: Python 3.10–3.13, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Uvicorn, SQLite / PostgreSQL.
- **Process Orchestration**: Centralized runner with `tree-kill` clean process lifecycle management.
