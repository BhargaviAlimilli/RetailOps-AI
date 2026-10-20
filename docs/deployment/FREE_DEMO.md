# Free demonstration hosting

The user selected free hosting plans with a US$1 monthly budget. The Cloud Run / Cloud SQL design remains an optional paid architecture; Cloud SQL is not used for this release. Budget alerts do not impose a spending cap.

## Release layout

- Render Free Docker web service, Singapore, 512 MB memory, one process.
- Neon Free PostgreSQL 17, Singapore, isolated `retailops_demo` database with synthetic data only. The project is `aged-dream-41430057`.
- `infra/Dockerfile.demo` builds React and the API into one unprivileged image. The browser uses the same HTTPS origin for assets, API requests and streaming.
- Repository-root `.dockerignore` allows only build inputs. Local credentials, Git history and dependency directories do not enter the build context.
- `RETAILOPS_WEB_DIRECTORY=/app/web` enables static delivery. Only known client routes receive `index.html`; missing API routes/assets remain 404. Hashed assets have immutable caching; the HTML shell is revalidated.

Render settings: public source repository `BhargaviAlimilli/RetailOps-AI`, branch `feat/retailops-foundation`, Dockerfile `infra/Dockerfile.demo`, repository-root build context, Free compute, Singapore, and health path `/api/v1/ready`. Do not choose a paid compute plan, disk, database or one-off job.

Set `RETAILOPS_ENVIRONMENT=production`, exact `RETAILOPS_ALLOWED_HOSTS` / `RETAILOPS_CORS_ORIGINS`, `RETAILOPS_DATABASE_TIMEOUT_SECONDS=20`, and a secret `RETAILOPS_DATABASE_URL` using the direct TLS Neon endpoint. Direct connections also support migrations and durable checkpoints. Store the DSN only in the hosting environment and ignored local environment files; never in source or images.

The first release leaves `RETAILOPS_AI_PROVIDER=disabled` and `RETAILOPS_RAG_ENABLED=false`. Gemini has separate metered usage and is not made free by choosing free hosting. Enabling it and verifying a live hosted answer requires an explicitly approved provider configuration and remaining paid-call allowance. Retail transactions, persisted conversations, MCP and checkpoint infrastructure remain implemented; AI-dependent actions report unavailable while disabled.

## Database and access

This deployment uses a new empty database, verified before migrations and synthetic seeding. It does not copy the local demo's private documents, conversations or sessions. A distinct random demo password is stored only in ignored `backend/.env.deployment`; it is not required in the web service environment. Demo login emails remain `manager@retailops.demo`, `analyst@retailops.demo` and `admin@retailops.demo`. Do not publish the password in project documentation.

Run database migrations as an explicit release action. Never rerun automatic empty-database preparation against populated or non-demo data. The seed refuses unknown existing data. Preserve this database across web-service rebuilds; container storage is ephemeral.

## Free-plan limits

Free web services and database computes sleep when idle. A cold request can take longer; this is a portfolio demo, with no uptime or latency commitment. Render's free compute allowance is shared with other free services in the workspace. Exhausting free quotas may suspend service. Free Neon storage/compute limits apply; do not upgrade automatically.

Keep tokens and account credentials out of browser screenshots, logs, build arguments and uploaded source. Backend authentication and manager authorization remain mandatory even though the HTTPS login page is public. Hosting free tiers are not a replacement for production recovery, monitoring, identity management or a security review.
