# RetailOps AI development instructions

## Repository and architecture
- `frontend/`: React 19, strict TypeScript, Vite; server state belongs in TanStack Query.
- `backend/`: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic; PostgreSQL is the source of truth.
- `docs/IMPLEMENTATION_PROGRESS.md`: factual progress and verification log.
- Keep routes thin; put business transactions in services and typed database access in repositories.
- Use Decimal/Numeric for money and timezone-aware UTC timestamps. Validate API boundaries with Pydantic and Zod.

## Workflow
- Inspect Git status and relevant code before editing; preserve existing work.
- Work on a feature branch. Make small Conventional Commits at verified milestones.
- Before each commit, review the diff, run applicable checks, scan for secrets, and stage explicit paths.
- Never invent passing checks, data, model output, citations, or deployment claims.
- Never push, force-push, reset history, provision paid resources, call paid APIs, or migrate non-demo data without explicit approval.

## Commands (once the foundation is installed)
- Backend: `cd backend`; `python -m venv .venv`; `.venv/Scripts/python -m pip install -e ".[dev]"`.
- Backend checks: `.venv/Scripts/python -m ruff check .`, `.venv/Scripts/python -m ruff format --check .`, `.venv/Scripts/python -m pytest`.
- Backend development: `.venv/Scripts/python -m uvicorn app.main:app --reload`.
- Frontend: `cd frontend`; `npm ci`; `npm run dev`.
- Frontend checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
- Database: `docker compose up -d db`; migrations and seed commands will be documented when implemented.

## Security and completion
- Never commit secrets, local environment files, private data, generated builds, or dependency directories.
- Enforce authentication and roles on the backend; UI restrictions alone are insufficient.
- Inventory changes require an audited transaction. Purchase-order approval requires an explicit authorized action and idempotency.
- Treat retrieved documents and AI text as untrusted; never execute arbitrary SQL or model-generated code.
- A feature is complete only with real integrated behavior, relevant passing tests, loading/error/empty states, accurate docs, and a scoped commit.
