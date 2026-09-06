# LocalScope — Local SEO, Rankings & Reputation Operating System

> **Local SEO, Rankings & Reputation in One Place**

LocalScope is an enterprise-grade Local SEO management and automation SaaS platform built for local businesses, franchises, and marketing agencies.

---

## Quick Start (Single Terminal Command)

Start both **Frontend** and **Backend** simultaneously from the project root:

```bash
npm run dev
```

### Terminal Output Preview

```text
╔══════════════════════════════════════════════╗
║          LocalScope Development              ║
╚══════════════════════════════════════════════╝

Starting services...

[FRONTEND] Starting Vite Dev Server...
[BACKEND]  Starting FastAPI Uvicorn Server...

[FRONTEND] ✓ Running at http://localhost:5173
[BACKEND]  ✓ Running at http://localhost:8000 (API Docs: http://localhost:8000/docs)

✓ LocalScope development environment ready
```

---

## Service URLs

| Service | Local URL | Description |
| :--- | :--- | :--- |
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | React 18 + Vite SaaS Dashboard |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI REST API |
| **API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI Documentation |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Backend status health check |

---

## Available Development Commands

Run from the root directory:

- `npm run dev`: Starts **both** Frontend and Backend concurrently with prefixed logs.
- `npm run dev:frontend`: Starts **only** the frontend Vite development server.
- `npm run dev:backend`: Starts **only** the backend FastAPI server.
- `npm run install:all`: Installs all root, frontend, and backend dependencies.
- `npm run build:frontend`: Builds the production bundle for the frontend.

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts, Lucide Icons.
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Uvicorn, SQLite/PostgreSQL.
- **Process Orchestration**: Node.js centralized runner with `tree-kill` clean process termination.
