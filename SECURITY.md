# RetailOps AI security status

This is a local synthetic demonstration, not a production deployment. Do not expose the Vite development server or local API publicly.

## Implemented controls
- Backend bearer sessions: random tokens, SHA256-only persistence, expiry/revocation, active-user checks; browser stores tokens in memory only.
- Salted PBKDF2-SHA256 password hashes with 600,000 rounds and constant-time comparison. Missing accounts use equivalent verification work.
- Backend manager/admin write checks, including service-layer checks for catalog/stock/purchase mutations. Analyst APIs cannot write by hiding or bypassing UI buttons.
- Database transactions, row/advisory locks, replay validation and immutable API audit/movement history. Supplier prices and quantity terms are validated server-side. Explicit internal approval and receipt are separate actions.
- Pydantic/Zod boundaries, decimal-safe finance, escaped literal searches and parameterized SQLAlchemy queries. AI read tools are explicitly allowlisted and cannot approve purchases or mutate inventory.
- Conversations enforce user ownership on the backend. Database-backed generation reservations and rolling allowances bound requests; provider deadlines, output limits and cancellation cleanup bound work. Request IDs replay saved replies without another generation.
- AI Markdown rejects raw HTML, sanitizes rendered content and blocks remote images. Model text and tool requests cannot execute business actions. Gemini defaults to disabled; local credentials alone do not enable calls.
- Private documents enforce owner filters for ingestion/list/source/search/delete. Uploads accept UTF-8 `.txt`/`.md` up to 100,000 bytes; PDF/binary and remote URL/path ingestion are rejected. Request bodies are bounded to 1 MiB before parsing, with a ten-second receive deadline.
- Durable document/generation allowances and bounded context/results limit resource use. LangGraph run leases, cross-run admission limits and idempotent domain mutations support cancellation/recovery. Approval requires a separate authenticated manager action with a reason; resumed conversational text cannot supply that authorization.
- MCP exposes only fixed read endpoints with a current session token. It rejects redirects and insecure remote HTTP origins, validates inputs/outputs and never returns raw transport errors.
- Explicit host/CORS configuration, no credential cookies (bearer authentication does not rely on ambient cookies), bounded login work/rates, database pool/statement deadlines, request IDs and redacted errors/log categories.
- Local PostgreSQL binds to loopback; test schemas use a separately named disposable database. Seed refuses non-demo targets and unrecognized data. Local secrets/dependencies/builds/traces are ignored by Git.

## Boundaries and limitations
The demo has one retail organization. All authenticated roles can view its stores, sales and supplier costs; conversations, documents and agent runs are private to their owner. No multi-organization isolation or per-store role scoping is claimed. Prompt instructions cannot guarantee that a model will never make an unsupported statement: grounding and citations support human verification, while backend permission/transaction boundaries enforce action safety independently of model compliance.

Login protection is process-local, resets on restart, and requires a shared proxy/gateway limiter before multiple production workers. Statement deadlines are not whole-request deadlines; report/list query batching and aggregate request budgets remain performance-hardening work. Development host defaults must be configured for a real deployment behind HTTPS; database superuser demo credentials must be replaced by least-privilege migration/runtime users. Backups, production monitoring and external penetration testing have not been performed.

Do not commit credentials or ask a model to execute unrestricted SQL/code. No paid model calls, billable infrastructure, non-demo migrations, remote pushes or deployments are authorized automatically.

Security tests cover roles, ownership, expiry/revocation, password handling, redaction, login/request limits, database outages/deadlines, transaction rollback, concurrent retry safety, unsafe tools, UTF-8/upload bounds, malformed streams and checkpoint recovery. The bounded corpus uses synchronous HTTP ingestion; larger deployments need queue/backpressure, shared embedding-query concurrency, least-privilege accounts and backup/load/operational review. See `docs/IMPLEMENTATION_PROGRESS.md` for actual commands/results; a passing local suite is not a production security certification.
