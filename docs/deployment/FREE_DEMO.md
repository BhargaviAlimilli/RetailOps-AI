# Free demonstration hosting

Live HTTPS URL: **https://retailops-ai-bhargavi.onrender.com**. Render service ID: `srv-dbbeq1m7bikc738aclig`. The deployed application release is commit `4a0244a`; [55 deployed HTTPS checks](../verification/deployment.json) and [all five hosted CI jobs](https://github.com/BhargaviAlimilli/RetailOps-AI/actions/runs/39370145943) passed for that release. Gemini and RAG are now enabled and verified ([hosted AI E2E evidence](../verification/hosted-ai-e2e.json)).

The user selected free hosting plans with a US$1 monthly budget. The Cloud Run / Cloud SQL design remains an optional paid architecture; Cloud SQL is not used for this release. Budget alerts do not impose a spending cap.

## Release layout

- Render Free Docker web service, Singapore, 512 MB memory, one process.
- Neon Free PostgreSQL 17, Singapore, isolated `retailops_demo` database with synthetic data only. The project is `aged-dream-41430057`.
- `infra/Dockerfile.demo` builds React and the API into one unprivileged image. The browser uses the same HTTPS origin for assets, API requests and streaming.
- Repository-root `.dockerignore` allows only build inputs. Local credentials, Git history and dependency directories do not enter the build context.
- `RETAILOPS_WEB_DIRECTORY=/app/web` enables static delivery. Only known client routes receive `index.html`; missing API routes/assets remain 404. Hashed assets have immutable caching; the HTML shell is revalidated.

Render settings: public source repository `BhargaviAlimilli/RetailOps-AI`, branch `feat/retailops-foundation`, Dockerfile `infra/Dockerfile.demo`, repository-root build context, Free compute, Singapore, and health path `/api/v1/ready`. Do not choose a paid compute plan, disk, database or one-off job.

Set `RETAILOPS_ENVIRONMENT=production`, exact `RETAILOPS_ALLOWED_HOSTS` / `RETAILOPS_CORS_ORIGINS`, `RETAILOPS_DATABASE_TIMEOUT_SECONDS=20`, and a secret `RETAILOPS_DATABASE_URL` using the direct TLS Neon endpoint. Direct connections also support migrations and durable checkpoints. Store the DSN only in the hosting environment and ignored local environment files; never in source or images.

The initial release disabled AI. With explicit approval, the deployed settings now enable `RETAILOPS_AI_PROVIDER=gemini` and `RETAILOPS_RAG_ENABLED=true`, using `gemini-3.1-flash-lite`, `gemini-embedding-001`, native JSON streaming, zero retries and a 1,024-token output cap. Google initially rejected embeddings with HTTP 402 because the linked paid tier required at least US$5 prepayment. The user approved unlinking billing only for the RetailOps Google project, returning it to the Gemini free tier. Render and Neon remain free. Free-tier quotas and Google data-use terms apply; use fictional demo content and do not upload private business/customer data.

Deployed per-user daily allowances are two chat turns, three retrieval queries and two document ingestions; document size is capped at 5,000 characters, ten chunks and five documents per user. These app limits are not a monetary billing cap if Google billing is re-enabled. The verification used the manager's ingestion/retrieval allowances, so new indexing/search requests may be limited until their rolling windows expire. Configuration deployment `dep-dbbl7mtg1s2s739bovd0` runs unchanged application source `4a0244a`.

The real hosted scenario indexed a fictional policy, retrieved its source excerpt, streamed a tool-backed cited answer, reopened/replayed the saved answer, and prepared a cited replenishment proposal requiring explicit manager confirmation. Separate receiving added exactly 30 demo units once. Twenty-two API assertions check SQL revenue agreement, source ownership, replay/idempotency, stock behavior and analyst access denial. No external supplier order was transmitted. This is a single synthetic scenario, not a general accuracy or load test.

## Database and access

This deployment uses a new empty database, verified before migrations and synthetic seeding. It does not copy the local demo's private documents, conversations or sessions. A distinct random demo password is stored only in ignored `backend/.env.deployment`; it is not required in the web service environment. Demo login emails remain `manager@retailops.demo`, `analyst@retailops.demo` and `admin@retailops.demo`. Do not publish the password in project documentation.

Run database migrations as an explicit release action. Never rerun automatic empty-database preparation against populated or non-demo data. The seed refuses unknown existing data. Preserve this database across web-service rebuilds; container storage is ephemeral.

## Free-plan limits

Free web services and database computes sleep when idle. A cold request can take longer; this is a portfolio demo, with no uptime or latency commitment. Render's free compute allowance is shared with other free services in the workspace. Exhausting free quotas may suspend service. Free Neon storage/compute limits apply; do not upgrade automatically.

Keep tokens and account credentials out of browser screenshots, logs, build arguments and uploaded source. Backend authentication and manager authorization remain mandatory even though the HTTPS login page is public. Hosting free tiers are not a replacement for production recovery, monitoring, identity management or a security review.
