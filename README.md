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
- `npm run install:all`: Installs all root, frontend, and backend virtual environment dependencies.
- `npm run build:frontend`: Builds the production bundle for the frontend.

---

## Backend Environment Setup

### Supported Python Versions
- **Recommended**: Python 3.12 / 3.13
- **Supported Range**: Python 3.10 – 3.13
- *Note: Python 3.14 is a preview release with ecosystem wheel limitations; use Python 3.12/3.13 for stability.*

### Manual Backend Setup (Optional)
If running outside the root `npm run dev` orchestrator:

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create virtual environment with supported Python
py -3.13 -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate   # Linux/macOS

# 4. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. Run test suite or start the server
python test_api.py
python run.py
```

---

## Technology Stack

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts, Lucide Icons.
- **Backend**: Python 3.10-3.13, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Uvicorn, SQLite/PostgreSQL.
- **Process Orchestration**: Node.js centralized runner with `tree-kill` clean process termination.
