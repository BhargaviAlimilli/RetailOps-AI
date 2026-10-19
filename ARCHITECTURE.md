# RetailOps AI architecture

Status: design baseline; implementation status is tracked in `docs/IMPLEMENTATION_PROGRESS.md`.

## Application boundaries
A React 19/TypeScript SPA calls a versioned FastAPI REST API. TanStack Query owns server state; Redux Toolkit will hold shared UI preferences only where needed. React Hook Form and Zod validate forms. Reusable accessible components underpin the operations and AI workspaces.

FastAPI routes validate requests and enforce identity/roles. Services own business rules and transaction boundaries; repositories contain SQLAlchemy queries. PostgreSQL stores operational records, immutable movement/approval audit history, conversations, and document chunks. Alembic owns schema changes. Monetary values use NUMERIC/Decimal; API monetary values serialize as strings. All timestamps are UTC; reports use explicit date boundaries.

## Data and workflows (planned)
Users have administrator, manager, or analyst roles. Stores, categories, products, suppliers, and product-supplier terms support store inventory, sales and purchase orders. Inventory updates use row locks and immutable movements in the same transaction. Purchase orders follow validated transitions with separate approval records and idempotency keys. Initial demo scope is a single retail organization; per-user conversation and document access must still be enforced.

## AI boundaries (planned)
An explicit provider interface isolates model SDKs, timeouts, usage and normalized errors. No provider is enabled without configuration. SSE events have identifiers and explicit lifecycle/tool/citation payloads. Conversations persist before model calls, and cancellation must close upstream streams.

An allowlisted tool registry validates arguments, permissions and resource limits. Tools query services, never model-generated SQL. LangGraph will orchestrate evidence gathering and persisted approval interruption/resumption. Model output cannot approve a purchase order.

RAG validates uploads, extracts text, chunks with provenance, generates configured embeddings, and stores vectors with pgvector. BM25 and vector rankings combine through RRF; optional reranking must be evaluated rather than presumed better. Citation references must point to retrieved accessible chunks. Retrieved text is evidence, never executable instructions.

## Deployment (planned)
Local Docker Compose provides PostgreSQL/pgvector. Containerized FastAPI targets Cloud Run with Cloud SQL, Secret Manager and structured logs. Frontend hosting is independently deployable. GitHub Actions will check formatting, types, tests, dependencies and builds. No cloud resources are provisioned by local setup.

## Decisions
- Build and verify the business application before AI orchestration.
- Use direct provider SDKs first; introduce LangChain only for a concrete need.
- Use real PostgreSQL integration tests rather than claiming SQLite proves PostgreSQL concurrency behavior.
- A missing provider or unavailable database must produce an explicit unavailable state, never fabricated demo results.
- Demo seed data will be synthetic, repeatable and guarded against non-demo databases.
