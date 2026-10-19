# RetailOps AI security status

This is a local synthetic demonstration, not a production deployment. Do not expose the Vite development server or local API publicly.

## Implemented controls
- Backend bearer sessions: random tokens, SHA256-only persistence, expiry/revocation, active-user checks; browser stores tokens in memory only.
- Salted PBKDF2-SHA256 password hashes with 600,000 rounds and constant-time comparison. Missing accounts use equivalent verification work.
- Backend manager/admin write checks, including service-layer checks for catalog/stock/purchase mutations. Analyst APIs cannot write by hiding or bypassing UI buttons.
- Database transactions, row/advisory locks, replay validation and immutable API audit/movement history. Supplier prices and quantity terms are validated server-side. Explicit internal approval and receipt are separate actions.
- Pydantic/Zod boundaries, decimal-safe finance, escaped literal searches and parameterized SQLAlchemy queries. Document uploads and operational AI tools are not implemented yet.
- Conversations enforce user ownership on the backend. Database-backed generation reservations and rolling allowances bound requests; provider deadlines, output limits and cancellation cleanup bound work. Request IDs replay saved replies without another generation.
- AI Markdown rejects raw HTML, sanitizes rendered content and blocks remote images. Model text and tool requests cannot execute business actions. Gemini defaults to disabled; local credentials alone do not enable calls.
- Explicit host/CORS configuration, no credential cookies (bearer authentication does not rely on ambient cookies), bounded login work/rates, database pool/statement deadlines, request IDs and redacted errors/log categories.
- Local PostgreSQL binds to loopback; test schemas use a separately named disposable database. Seed refuses non-demo targets and unrecognized data. Local secrets/dependencies/builds/traces are ignored by Git.

## Boundaries and limitations
The demo has one retail organization. All authenticated roles can view its stores, sales and supplier costs, while conversations are private to their owner. No multi-organization isolation or per-store role scoping is claimed. Document access and tool execution need their own permission checks as they are introduced. General AI replies have no live operational data or retrieved evidence; no grounding claim is made at this stage.

Login protection is process-local, resets on restart, and requires a shared proxy/gateway limiter before multiple production workers. Statement deadlines are not whole-request deadlines; report/list query batching and aggregate request budgets remain performance-hardening work. Development host defaults must be configured for a real deployment behind HTTPS; database superuser demo credentials must be replaced by least-privilege migration/runtime users. Backups, production monitoring and external penetration testing have not been performed.

Do not commit credentials or ask a model to execute unrestricted SQL/code. No paid model calls, billable infrastructure, non-demo migrations, remote pushes or deployments are authorized automatically.

Security tests cover roles, expiry/revocation, password handling, request validation redaction, login limits, database outages/deadlines, transaction rollback and concurrent retry safety. See `docs/IMPLEMENTATION_PROGRESS.md` for actual commands/results; a passing local suite is not a production security certification.
