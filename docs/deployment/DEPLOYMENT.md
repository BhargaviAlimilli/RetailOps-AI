# Deployment and local container preview

The authorized portfolio deployment uses [Render Free and Neon Free](FREE_DEMO.md). The GCP files below remain optional preparations: no paid GCP resource has been provisioned, and no paid model request is part of CI. Cloud manifests contain deliberate `REPLACE_*` values and must be reviewed before use.

## Local synthetic preview

Prerequisites: Docker Engine with Compose, enough space for PostgreSQL and both images. Set `POSTGRES_PASSWORD` to a locally generated URL-safe value (letters/digits/underscore/hyphen) and `RETAILOPS_DEMO_PASSWORD` to a distinct local password of at least 12 characters. Keep both outside Git. In PowerShell, `$env:POSTGRES_PASSWORD` and `$env:RETAILOPS_DEMO_PASSWORD` supply these variables.

From the repository root:

```text
docker compose -f infra/compose.preview.yml build
docker compose -f infra/compose.preview.yml up -d db
docker compose -f infra/compose.preview.yml run --rm backend python -m alembic upgrade head
docker compose -f infra/compose.preview.yml run --rm backend python -m app.db.seed
docker compose -f infra/compose.preview.yml up -d backend frontend
```

Visit `http://127.0.0.1:8080`. Accounts use `manager@retailops.demo`, `analyst@retailops.demo`, and `admin@retailops.demo` with the configured demo password. The seed checks development environment, the `retailops_demo` name, and empty/recognized synthetic data; it refuses an unrecognized populated database. It never resets data.

The database has no published host port in this preview. API requests pass through nginx on the same origin; nginx disables response buffering for real SSE. The backend runs as an unprivileged user. Frontend build dependencies do not ship in its nginx runtime image. Stop with `docker compose -f infra/compose.preview.yml down`; retaining the named volume preserves data. Removing that volume is destructive and is deliberately omitted here.

The preview disables AI by default. Enabling Gemini generation or document embeddings requires explicit authorized configuration and may incur API costs. A working provider configuration is distinct from a verified live model demonstration.

## GCP design

`infra/cloudrun-backend.yaml` and `infra/cloudrun-frontend.yaml` prepare two Cloud Run services. The frontend proxies `/api/` to the API service. Cloud SQL PostgreSQL must support the `vector` extension. Backend migrations run as an explicit release operation, never in each web replica at startup. Cloud SQL backups, point-in-time recovery, maintenance windows, and recovery testing remain operator responsibilities.

Use a dedicated backend service account with `roles/cloudsql.client` and access only to the required Secret Manager secret versions. Store the full `postgresql+psycopg://...` database URL in Secret Manager; percent-encode password characters and use the attached `/cloudsql/PROJECT:REGION:INSTANCE` socket. Do not put passwords, API keys, or service-account JSON in manifests/images. Optional Gemini credentials belong in a separately authorized secret reference; keep the model explicitly configured. Frontend containers receive only a backend origin, never a provider key.

The prepared nginx proxy forwards application Bearer authentication. It does **not** mint a Google IAM identity token. Therefore the API transport must be reachable by this proxy and its application authentication remains mandatory. A private Cloud Run API instead requires an authenticated gateway/proxy that mints and refreshes Google identity tokens; do not assume the provided static nginx configuration supports that architecture. Review ingress and IAM before deployment.

After explicit approval, an operator would create/review the project resources, build and scan immutable images, run migrations against an approved target with backups, fill in manifest hostnames/service-account/image/Cloud SQL values, apply service definitions, and configure transport access. Those billable and externally visible operations are not performed by these files or the verification workflow. Do not run the synthetic seed against production.

## Production checks and limits

- Set exact allowed hosts and CORS origins; terminate HTTPS at Cloud Run.
- Validate `/api/v1/health` for liveness and `/api/v1/ready` for database readiness. Readiness never calls a paid provider.
- Verify nginx streaming through the deployed endpoint, cancellation, proxy deadlines, secure login, analyst rejection of writes, and database rollback on failed receiving.
- Capacity-plan connection pools across replicas. The initial maximum of three API replicas is a template limit, not a measured sizing recommendation.
- Collect structured logs without request bodies, document text, tokens, or provider errors. Configure retention, alerts, and access control separately.
- Restrict budgets/quotas and monitor generation/embedding spend before enabling paid features.
- Add a managed identity provider, edge abuse protection, backup restoration drills, and deployment rollback validation before treating this portfolio implementation as an operated production service.

## CI

`.github/workflows/verify.yml` defines frontend formatting/lint/type/tests/build/audit, backend lint/format/tests/audit with real pgvector PostgreSQL, seeded Playwright journeys, Docker image builds, and Git history secret scanning. No deployment job or cloud credentials are configured. Browser traces are retained for only three days on failure and use synthetic data. [GitHub run 39370145943](https://github.com/BhargaviAlimilli/RetailOps-AI/actions/runs/39370145943) passed all five jobs for deployed application commit `4a0244a`; later releases must retain their own verification evidence.
