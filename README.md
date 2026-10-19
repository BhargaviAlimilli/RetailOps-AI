# RetailOps AI

A retail operations application being built incrementally for a senior full-stack engineering demonstration: React/TypeScript, FastAPI, PostgreSQL, and a grounded AI workspace with explicit human approval for business actions.

## Current functionality

The local core retail application is functional: sign-in and backend roles, database-calculated dashboard, product catalog/creation, supplier terms, inventory filters/audited adjustments, sales reporting, and purchase drafts with explicit approval and receiving. Reports and actions use PostgreSQL rather than static fixtures in the UI. The demo data is clearly synthetic.

Gemini AI Companion is the next implementation milestone. Streaming model verification, RAG, agent tools/checkpoints, CI/cloud deployment and interview-ready end-to-end AI demonstrations are not complete. See [verified progress](docs/IMPLEMENTATION_PROGRESS.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md).

![Retail dashboard](docs/screenshots/retail-dashboard-desktop.png)

![Internal purchase approval and receiving](docs/screenshots/purchase-received-desktop.png)

## Local setup (PowerShell)

Requires Node 22.12+ (verified on 24.19), Python 3.12+ and a running Docker Desktop.

```powershell
# Repository root: disposable demo database, bound to loopback only.
docker compose up -d db

cd backend
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -c constraints.txt -e ".[dev]"
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env: set RETAILOPS_DEMO_PASSWORD to a unique 12-256 character password.
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.db.seed
.venv/Scripts/python -m app
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173 and sign in with a seeded demo account below. Public connection status is at `/system`. Vite forwards `/api` to FastAPI at http://127.0.0.1:8000. API documentation is at http://127.0.0.1:8000/docs in development. On Windows use `python -m app`: its explicit Selector loop is required for psycopg with Uvicorn 0.54. On POSIX replace `.venv/Scripts/python` with `.venv/bin/python`.

This machine has an older roaming npm that crashes during peer resolution. If encountered, use the current bundled CLI: `node "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js" ci` (or other npm command). No global npm changes are required.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Never commit local environment files. The checked-in credentials are disposable local-demo examples only.

| Variable | Purpose |
| --- | --- |
| `RETAILOPS_ENVIRONMENT` | `development`, `test` or `production`; production disables API docs |
| `RETAILOPS_DEMO_PASSWORD` | Unique local-only password used when seeding demo accounts; secret-safe and never sent to the frontend |
| `RETAILOPS_DATABASE_URL` | PostgreSQL SQLAlchemy URL using `postgresql+psycopg://`; unset means readiness returns 503 |
| `RETAILOPS_CORS_ORIGINS` | JSON array of explicit permitted browser origins |
| `RETAILOPS_ALLOWED_HOSTS` | JSON array of accepted API hostnames; defaults to localhost/loopback |
| `RETAILOPS_DATABASE_TIMEOUT_SECONDS` | Readiness probe deadline; default 3 seconds |
| `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Root Compose settings; local defaults shown in `.env.example` |

Use IPv4 `127.0.0.1` for the database on this Windows host; `localhost` caused a stalled connection during initial verification. If overriding Compose credentials/port, update the backend URL to match. Named-volume data persists across container restarts. The seed refuses non-development environments, any database name except `retailops_demo`, and unrecognized nonempty data. Repeating it preserves an already seeded workspace.

## Demo accounts

| Email | Access |
| --- | --- |
| `manager@retailops.demo` | Reports, catalog creation, stock adjustments, purchase approval and receiving |
| `analyst@retailops.demo` | Read-only reports/catalog/inventory/purchases; direct writes return 403 |
| `admin@retailops.demo` | Same current business write permissions as manager |

Use the password you set in `backend/.env` before seeding. This workspace already has a unique generated local password there; it is not committed or displayed in this document. Browser tokens remain in memory, expire after 8 hours server-side, and are revoked on logout. Refreshing the browser requires a fresh sign-in.

Seed data includes three stores, twelve products, supplier lead-time/pack variations, 90 days of sales, stockouts, an intentional decline scenario and a reconciled inventory ledger. It represents fictional operations, not a real retailer.

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

Browser tests use real services rather than intercepted responses and capture desktop/mobile screenshots. Retail journeys read the local demo password from ignored configuration, create synthetic purchase orders, approve/receive them and record audited stock changes. They run sequentially against the shared demo database; concurrent transaction behavior is tested in isolated PostgreSQL schemas. Without a configured seed password, the retail browser journeys explicitly skip. Unit tests explicitly mock unavailable dependencies. Database integration fixtures require a configured disposable demo/test server, create unique migrated schemas inside `retailops_test`, and clean up only those test schemas. Run backend commands from `backend/` so its local `.env` is loaded; otherwise integration tests explicitly skip.

## Architecture, security and limitations

- [Architecture and trade-offs](ARCHITECTURE.md)
- [Development conventions](AGENTS.md)

The core retail app is locally verified, but the full AI interview demonstration is unfinished. Gemini streaming, document ingestion/retrieval/citations, LangGraph, AI purchase proposals, MCP showcase, CI and deployment remain. The current explicit human purchase approval workflow works independently of AI. No model call, external supplier order, cloud resource or production deployment has been performed.

Security is enforced in the API and services, including analyst write denial, audited transactions, validated authoritative supplier pricing, idempotency/concurrency checks, request/database limits and secret-safe errors. See [security assumptions](SECURITY.md) and [backend safeguards](backend/SECURITY.md). The demo is a single organization; all authenticated roles can read its operational data and supplier costs. Do not expose development servers publicly. Distributed rate limiting, HTTPS/proxy configuration, hardened deployment accounts and production secret management are deployment work.

The planned deployment design uses Cloud Run, Cloud SQL and Secret Manager. Provisioning and remote pushes require separate explicit approval. The user's selected AI provider is Gemini; credentials and approval for any paid verification calls will be requested only once the integration is concrete and reviewable.
