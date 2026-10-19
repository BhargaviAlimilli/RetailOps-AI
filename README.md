# RetailOps AI

A retail operations application being built incrementally for a senior full-stack engineering demonstration: React/TypeScript, FastAPI, PostgreSQL, and a grounded AI workspace with explicit human approval for business actions.

## Current functionality

The application foundation runs locally: responsive React workspace, validated API client, live service status, FastAPI liveness/readiness, structured request logs, PostgreSQL/pgvector and an Alembic migration baseline. Business modules and AI are planned, not implemented yet. See [verified progress](docs/IMPLEMENTATION_PROGRESS.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md).

![Desktop foundation](docs/screenshots/foundation-desktop.png)

## Local setup (PowerShell)

Requires Node 22.12+ (verified on 24.19), Python 3.12+ and a running Docker Desktop.

```powershell
# Repository root: disposable demo database, bound to loopback only.
docker compose up -d db

cd backend
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -c constraints.txt -e ".[dev]"
Copy-Item .env.example .env
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite forwards `/api` to FastAPI at http://127.0.0.1:8000. API documentation is at http://127.0.0.1:8000/docs in development. On Windows use `python -m app`: its explicit Selector loop is required for psycopg with Uvicorn 0.54. On POSIX replace `.venv/Scripts/python` with `.venv/bin/python`.

This machine has an older roaming npm that crashes during peer resolution. If encountered, use the current bundled CLI: `node "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js" ci` (or other npm command). No global npm changes are required.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Never commit local environment files. The checked-in credentials are disposable local-demo examples only.

| Variable | Purpose |
| --- | --- |
| `RETAILOPS_ENVIRONMENT` | `development`, `test` or `production`; production disables API docs |
| `RETAILOPS_DATABASE_URL` | PostgreSQL SQLAlchemy URL using `postgresql+psycopg://`; unset means readiness returns 503 |
| `RETAILOPS_CORS_ORIGINS` | JSON array of explicit permitted browser origins |
| `RETAILOPS_ALLOWED_HOSTS` | JSON array of accepted API hostnames; defaults to localhost/loopback |
| `RETAILOPS_DATABASE_TIMEOUT_SECONDS` | Readiness probe deadline; default 3 seconds |
| `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Root Compose settings; local defaults shown in `.env.example` |

Use IPv4 `127.0.0.1` for the database on this Windows host; `localhost` caused a stalled connection during initial verification. If overriding Compose credentials/port, update the backend URL to match. Named-volume data persists across container restarts. No seed command or demo accounts exist yet.

## Verification

```powershell
cd backend
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest
# Optional read-only integration probe against the migrated disposable database:
$env:RETAILOPS_TEST_DATABASE_URL="postgresql+psycopg://retailops:retailops_local_only@127.0.0.1:5432/retailops_demo"
.venv/Scripts/python -m pytest tests/test_postgres.py
.venv/Scripts/python -m pip_audit --local --skip-editable

cd ../frontend
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
npm audit
npx playwright install chromium
# Start the backend/database first; Playwright starts Vite automatically.
npm run test:e2e
```

Browser tests use real services rather than intercepted responses and capture desktop/mobile screenshots. Unit tests explicitly mock unavailable dependencies; real-database checks are opt-in and report a skip when not configured.

## Architecture, security and limitations

- [Architecture and trade-offs](ARCHITECTURE.md)
- [Development conventions](AGENTS.md)

This is a development foundation, not an interview-ready business application or production deployment. Authentication, operational schema/seed/APIs, AI streaming, RAG, agents, purchase approvals, CI and cloud deployment are pending. Do not expose the development servers publicly. Cloud Run/Cloud SQL/Secret Manager are the planned deployment design; nothing has been provisioned or deployed. Provider credentials and approval for paid model calls will be required later. Remote pushes require separate approval.
