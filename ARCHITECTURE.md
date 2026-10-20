# RetailOps AI architecture

Status: implemented local architecture; verification and deployment boundaries are tracked in `docs/IMPLEMENTATION_PROGRESS.md`.

## Application boundaries
A React 19/TypeScript SPA calls a versioned FastAPI REST API. TanStack Query owns server state; Redux Toolkit holds the in-memory bearer session. React Hook Form and Zod validate forms. Reusable accessible components underpin the operations and AI workspaces.

FastAPI routes validate requests and enforce identity/roles. Services own business rules and transaction boundaries; repositories contain SQLAlchemy queries. PostgreSQL stores operational records, immutable movement/approval audit history, conversations, and document chunks. Alembic owns schema changes. Monetary values use NUMERIC/Decimal; API monetary values serialize as strings. All timestamps are UTC; reports use explicit date boundaries.

## Data and workflows
Users have administrator, manager, or analyst roles. Stores, categories, products, suppliers, and product-supplier terms support store inventory, sales and purchase orders. Inventory updates use row locks and immutable movements in the same transaction. Purchase orders follow validated transitions with separate approval records and idempotency keys. Initial demo scope is a single retail organization; per-user conversation and document access must still be enforced.

## AI boundaries
An explicit provider interface isolates model SDKs, timeouts, usage and normalized errors. No provider is enabled without configuration. SSE events have identifiers and explicit lifecycle/tool/citation payloads. Conversations persist before model calls, and cancellation must close upstream streams.

An allowlisted tool registry validates arguments, permissions and resource limits. Chat exposes read-only tools with at most four calls and two model rounds. Tools query services, never model-generated SQL. LangGraph orchestrates deterministic evidence gathering and persisted approval interruption/resumption. Model output cannot approve a purchase order. PostgreSQL checkpoint tables are created by Alembic, not runtime DDL. Short leases, bounded cleanup and shared admission locks protect recovery and checkpoint connections.

RAG accepts bounded UTF-8 text/Markdown uploads, chunks normalized text with offsets, generates Gemini embeddings and stores vectors with pgvector. Exact cosine search suits the bounded per-user corpus. BM25 and vector rankings combine through RRF; optional lexical-overlap reranking is explicitly deterministic. Citation references point to retrieved accessible chunks. Retrieved text is evidence, never executable instructions. Durable audit allowances survive document deletion. The upstream native JSON array is decoded incrementally into application SSE; incomplete/invalid JSON and embedded provider errors fail safely. No output pacing timers simulate token streaming.

## Deployment preparation
Local Docker Compose provides PostgreSQL/pgvector. Built FastAPI/nginx images and reviewed templates target Cloud Run with Cloud SQL, Secret Manager and structured logs. GitHub Actions defines formatting, types, PostgreSQL tests, browser journeys, audits, image builds and secret scanning. Cloud infrastructure has not been provisioned, and the workflow has not executed remotely. A standard MCP stdio facade calls four fixed authenticated read APIs without bypassing existing permissions.

## Decisions
- Build and verify the business application before AI orchestration.
- Use direct provider SDKs first; introduce LangChain only for a concrete need.
- Use real PostgreSQL integration tests rather than claiming SQLite proves PostgreSQL concurrency behavior.
- A missing provider or unavailable database must produce an explicit unavailable state, never fabricated demo results.
- Demo seed data will be synthetic, repeatable and guarded against non-demo databases.
