# Incremental implementation plan

Each milestone is independently reviewed, checked and committed. Finish essential phase behavior before advancing.

0. Audit repository, establish branch/identity, conventions, architecture and progress log.
1. Create tested FastAPI and React application foundation, health/readiness API, typed client, PostgreSQL/pgvector Compose service and migration baseline; verify local startup.
2. Add schema/migrations, secure demo identity, deterministic synthetic seed, products/stores/suppliers, transactional inventory, sales aggregates and dashboard, purchase-order state machine and UI. Verify permission and transaction boundaries.
3. Persist conversations, implement configured provider integration and SSE contract, add accessible streaming workspace, cancellation and failure handling. Unit tests use a mock provider; a real provider demo needs credentials and approval for paid calls.
4. Add validated document ingestion, embeddings, authorized pgvector/BM25/RRF retrieval, citations and reproducible retrieval evaluation.
5. Add allowlisted operational tools and LangGraph checkpoints; verify the sales-decline to replenishment/explicit approval journey with idempotency and audit history.
6. Add a documented MCP integration, reusable AI showcase, evaluation, observability and security/performance hardening.
7. Add CI/CD checks, deployment configuration, screenshots and interview guides reflecting actual behavior; verify the full local demonstration.

## Dependencies and approval boundaries
- Available: Node 24.19, Python 3.12, Git, Docker CLI 29.4.
- Required locally: frontend npm dependencies, isolated backend environment, working PostgreSQL with pgvector.
- Docker Desktop currently reports that it cannot start; do not claim database integration passes until this is resolved.
- Later: Gemini or OpenAI credentials and embedding model selection; explicit authorization before paid calls.
- Later deployment: GCP project, billing, Cloud SQL, Secret Manager and deployment approval. No cloud provisioning now.
- Local commits are authorized; remote pushes require separate explicit approval.
