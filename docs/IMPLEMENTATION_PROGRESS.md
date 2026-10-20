# Implementation progress

## 2026-10-19 - Phase 0: repository audit and conventions

- Initial repository contains only `.git`, no tracked files and no commits; original branch `main`.
- Origin: `https://github.com/BhargaviAlimilli/RetailOps-AI.git`.
- Working branch: `feat/retailops-foundation`; repository-local author identity supplied by the user.
- Available runtimes: Node 24.19.0, Python 3.12.0, Docker CLI 29.4.0.
- Backend framework/test dependencies are not yet installed. Docker daemon reports `Docker Desktop is unable to start`.
- Added architecture baseline, incremental implementation plan, development conventions and ignore/editor settings.
- Verification: inspected Git state/configuration and runtimes; reviewed all foundation documents and `git diff --check` before commit.
- No implementation, database verification, AI calls, deployments or remote pushes are claimed at this milestone.
- Next: application foundation and health/readiness contracts; resolve local database availability before completing Phase 1.

## 2026-10-19 - Phase 1a: API foundation

- Added FastAPI app factory, versioned liveness/readiness endpoints, validated environment settings, structured JSON request logs, request IDs, explicit CORS/host checks and safe database failure responses.
- SQLAlchemy async PostgreSQL probe has a deadline, bounded pool, disposal and redacted driver failure logs. Configuration errors hide secret inputs.
- Added Python module startup using an explicit Selector loop on Windows; Uvicorn 0.54 otherwise creates a Proactor loop incompatible with psycopg.
- Added isolated dependencies and tested-version constraints. Upgraded only the virtual environment's pip after its initial audit reported vulnerabilities.
- Verification: Ruff lint and formatting; pytest **15 passed**, including the opt-in real PostgreSQL readiness test; `pip check` passed; `pip_audit --local --skip-editable` reported no known vulnerabilities after remediation.
- Live HTTP checks: `/api/v1/health` returned 200; `/api/v1/ready` returned 200 with the real local database, and 503 before the connection was usable.
- Review: a coding agent reviewed the foundation; identified secret-error rendering and Windows loop compatibility issues were corrected and verified.
- No business APIs, authentication, AI integrations or production deployment exist yet.

## 2026-10-19 - Phase 1b: PostgreSQL migration baseline

- Added local-only Docker Compose PostgreSQL 17/pgvector with a named volume, healthcheck and loopback port binding.
- Docker Desktop recovered after starting the installed desktop service; no reset or volume deletion was performed.
- Added Alembic async environment, Windows Selector runner, bounded connection timeout and initial pgvector extension revision.
- Verification: `docker compose config --quiet`, service startup, `pg_isready`, `alembic upgrade head` twice and `alembic current` (0001/head). Direct PostgreSQL queries confirmed extension `vector` and revision `0001`.
- Used IPv4 loopback explicitly: the earlier localhost connection stalled on this Windows host. The repeated IPv4 migration and HTTP readiness checks succeed.
- Downgrade deliberately preserves the potentially shared extension; it does not delete business data.

## 2026-10-19 - Phase 1c: connected React workspace

- Added React 19/strict TypeScript/Vite 8, Tailwind 4, React Router, TanStack Query and Zod runtime API validation.
- Added responsive workspace navigation, reusable button, honest module availability states, query cancellation/deadlines, live service cards, loading/error/retry states, skip link and keyboard navigation.
- No invented business metrics or AI output. Unimplemented navigation is visibly marked Planned and disabled.
- Verification: frontend lint, formatting, typecheck, 7 Vitest tests, production build and npm audit. Two Playwright tests passed against the real backend/database (desktop and mobile), including HTTP readiness, live UI status and no viewport overflow.
- Visually inspected both captured screenshots in `docs/screenshots/`; desktop and mobile layouts are readable without overflow.
- Tooling correction: older roaming npm 10.2 crashed in dependency peer resolution; the Node-bundled npm 11.17 succeeded. ESLint 10 replaced the now-unsupported v9 after verifying peer compatibility.
- Phase 1 foundation is functional. Remaining: business schema, identity and retail workflows (Phase 2), then AI/RAG/agents, hardening, CI and interview deliverables.

## 2026-10-19 - Phase 2a: schema, authentication and synthetic data

- `083e8ae` adds constrained relational retail tables, explicit Alembic migration and per-test isolated PostgreSQL schemas in a dedicated `retailops_test` database.
- `38880d0` adds salted PBKDF2-SHA256 passwords (600,000 rounds), opaque 8-hour sessions persisted only as SHA256 token hashes, revocation, active-user checks and manager/admin write roles.
- Guarded seed is development-only and restricted to `retailops_demo`; requires an explicitly supplied local password and refuses unrecognized nonempty data. Synthetic records include 3 stores, 12 products, 270 sales over 90 days, supplier terms, reconciled inventory movements, stockouts and purchase drafts/pending orders.
- Agent verification: migration upgrade/schema drift checks; 15 schema/health/database checks and 16 auth/seed/health checks passed in their scoped runs. Seed repeatability and inventory reconciliation verified in isolated tests. Real demo population is a separate next step.

## 2026-10-19 - Phase 2b: retail catalog and reporting APIs

- Added authenticated stores/categories/supplier terms/product list/detail, audited product creation with per-store zero balances, paginated literal-text product/inventory search, stock status filters, sales ledger and database-calculated dashboard.
- Reports use Decimal values, explicit UTC periods, same-length previous periods, complete daily series, store/category splits, zero-sale slow products and current inventory/purchase indicators. Recent workspace activity is explicitly organization-wide.
- Added secret-safe request validation responses. Invalid payloads cannot echo passwords in `input` fields.
- Independent review findings fixed: duplicate-SKU concurrency returns 409, same-name stores remain separate, non-UTC PostgreSQL sessions still produce UTC daily totals, unsupported extreme dates return 422.
- Verification: scoped Ruff lint/format; **20 tests passed** (7 real PostgreSQL reporting/product/security regressions and 13 calculation/input-validation tests). No skipped integration checks in this backend-directory run.
- Stock mutations and purchase workflow routes will land separately after their dedicated verification.

## 2026-10-19 - Phase 2c: stock and purchase workflows

- Added manager/admin stock adjustments with nonzero integer deltas, required reasons, reserved-stock protection, row locks, immutable movement/audit records and replay validation.
- Purchase drafts validate supplier associations, snapshotted authoritative cost, minimum quantities and pack sizes. The server requires explicit submit, approve/reject and receive actions; analyst API calls are forbidden.
- Approval history records the actor, decision and reason. Receiving atomically updates inventory and records movements; no external supplier submission is claimed.
- Request-key advisory locks plus per-resource row locks prevent duplicate execution and lost stock updates. Conflicting key reuse is rejected. Multi-product receipt failures roll back both quantities and order status.
- Purchase listing is paginated and server-filtered so older pending approvals cannot be hidden by a newest-record cap.
- Verification: **7 real PostgreSQL workflow tests passed**, including concurrent same-key requests, competing stock decrements, complete approval/receiving, supplier validation, older pending-order discovery and atomic failed-receipt rollback. Scoped Ruff checks passed.
- Independent service review found no double-application or partial-rollback defect; its reporting and pagination findings were corrected and covered separately.

## 2026-10-19 - Phase 2 security follow-up

- `bc94112` bounds login attempts (account/IP, bounded memory) and password verification concurrency; slots remain held until verification finishes even on cancellation.
- Database connections/pool acquisition/statements have deadlines; outages become generic 503 errors without driver details. Integrity conflicts remain business errors.
- Isolated test setup installs pgvector in durable public schema under an advisory lock to avoid concurrent teardown races.
- Agent checks: scoped Ruff passed; 17 scoped hardening tests passed, then 6 availability tests passed after adding an actual PostgreSQL statement-deadline regression. See `backend/SECURITY.md` for process-local limiter and timeout limits.

## 2026-10-19 - Phase 2 demo setup verification

- Seed CLI now reads the password through secret-safe Settings, including local `backend/.env`, rather than requiring a process-only environment variable.
- Generated a unique local demo password in ignored `backend/.env`; the value was neither printed nor committed. Accounts: `manager@retailops.demo`, `analyst@retailops.demo`, `admin@retailops.demo`.
- Actual `retailops_demo` migration and seed succeeded; second seed reported already seeded with no changes.
- Full backend verification after integration: Ruff lint passed, 41 Python files formatted, **59 tests passed**, and `alembic check` reported no new upgrade operations. Real integration checks executed with local PostgreSQL; no skipped tests in this run.

## 2026-10-19 - Phase 2d: integrated retail workspace

- `4bd86ad` adds in-memory Redux sessions, validated React Hook Form/Zod sign-in, bearer API client, logout/cache clearing and a protected-route foundation.
- Connected dashboard, sales, products, inventory, suppliers, purchases and settings behind sign-in. TanStack Query owns server data. Added reusable tables, accessible focus-trapped dialogs, real filters/pagination, loading/error/empty states and explicit decision/receipt forms.
- Catalog creation, inventory adjustments and purchase state actions update real PostgreSQL through validated APIs. Read-only analyst screens are backed by server write denial.
- Route-level lazy imports keep charts/forms out of initial sign-in load; production build has no oversized-chunk warning. Initial shared JS is about 328 kB before compression; dashboard chart chunk about 357 kB. These are build sizes, not fabricated runtime performance claims.
- Frontend checks after integration: lint/typecheck, **19 unit/component/API tests passed**, split production build. Real browser verification: **6 tests passed** across desktop/mobile, including live revenue equality with API, draft/submit/approve/receive, audited stock changes and analyst UI/API denial. Browser tests are sequential against shared synthetic data; concurrency is separately tested with isolated schemas.
- Visually reviewed dashboard and completed purchase screenshots; corrected encoded punctuation and disabled chart reveal animations so captures show complete data. Generated traces/reports remain ignored.
- Phase 2 essential local retail behavior is verified. Gemini was selected by the user; Phase 3 provider/conversation/SSE work is next. No model output, citations, agents, deployment or interview-ready AI demonstration is claimed yet.

## 2026-10-19 - Phase 3: persisted AI Companion integration

- `d67d93f` introduces a provider protocol and Google Gen AI adapter with typed results, structured validation, bounded retries/deadlines, explicit model selection and disabled automatic tool execution. `e71e13c` adds the conversation UI and authenticated SSE client.
- `6415ab9` adds migration 0003, private conversation/message APIs, stable message ordering, persisted partial/terminal replies, stale-lease recovery and request-ID replay without a second generation. Short database transactions reserve capacity before provider calls. Ownership, per-user/global concurrency and rolling request allowances are enforced on the backend.
- Provider follow-up sanitizes client-construction/malformed-output failures, bounds transport cleanup and preserves finish reasons. Cancellation cleanup retains and consumes background tasks with a separate deadline. Token-limit truncation is visible in the UI.
- `1d12046` connects the assistant route, authenticated configuration status, honest general-guidance limitations, whole-message clipboard feedback and desktop/mobile disabled-provider journeys. Corrected a duplicate copy control inside Markdown links and an ambiguous browser selector; added regression coverage. Remote Markdown images remain blocked and raw HTML is not rendered.
- Verification: backend Ruff lint and format checks passed (53 files); **84 tests passed** with real PostgreSQL integration enabled, including ownership, persistence/replay, cancellation at the first frame and after partial text, timeout cleanup, concurrency and generation allowances. Provider tests substitute the SDK and make no external requests.
- Local demo database reports Alembic **0003 (head)**; `alembic check` reports no new upgrade operations. No non-demo migration was performed.
- Frontend lint, typecheck and production build passed; **36 unit/component/client tests passed**. Full formatting check passed after correcting an existing conversation-test formatting issue. **8 real browser tests passed** across desktop/mobile, covering retail regression journeys and disabled AI with zero message writes. Screenshots show the unavailable state, not generated model output.
- Presence-only configuration check confirms local key/model values exist and provider remains **disabled**. No key value was printed, staged or committed. Staged secret-pattern scans and whitespace checks passed.
- Real Gemini streaming remains unverified and requires explicit approval for a bounded model call. RAG, operational tools, LangGraph/checkpoints, MCP, CI/cloud deployment and interview AI demonstrations remain subsequent work. Phase 3 is not claimed complete until a real response is verified.

## 2026-10-19 - Remaining implementation and authorized live verification

- User explicitly approved ten bounded generation requests and twelve embedding requests, then four additional generation requests. Verification used only fictional policy/demo questions, at most 1,024 output tokens per generation, and disabled retries. No cloud provisioning, remote push or deployment was authorized/performed.
- `fbe469a` adds migrations 0004/0005, private documents/chunks with vector(768), agent runs, reply evidence fields and standard LangGraph PostgreSQL checkpoints. Schema drift check reports no new operations. Tested dependency versions are constrained; Windows-only dependencies have platform markers.
- `f1b5b6e` adds owned text/Markdown ingestion, UTF-8 `.txt`/`.md` upload validation (100,000 bytes), chunk offsets, real Gemini embeddings, exact cosine retrieval, BM25/RRF and optional deterministic overlap reranking. Duplicate content is idempotent, processing leases reject stale attempts, and audit allowances survive deletion. Unsupported PDF/binary/remote-URL ingestion is explicitly rejected.
- Live RAG smoke: **three fictional policy documents indexed; two searches returned the expected source first**, using five successful actual embedding HTTP requests. Two earlier SDK-only attempts failed before any HTTP call: removed Vertex-only `auto_truncate` and added a real SDK conversion/HTTP MockTransport regression. `backend/fixtures/data/documents/evaluation_live.json` records the small test; it is not a broad quality or faithfulness benchmark. Offline comparison explicitly labels mock semantic rankings and compares keyword/vector/hybrid/reranked methods.
- `c5d03dc` wires bounded read-only model tools and actual policy context, typed arguments, saved citations/tool traces, independent result/source budgets, safe error handling and metadata-only latency/usage logs. Models cannot execute SQL/code or approve business actions.
- The replenishment graph reads actual SQL sales/stock/supplier evidence, deducts pending/approved inbound orders, respects minimums/packs and creates a pending internal order. Standard PostgreSQL checkpoints preserve the explicit approval interrupt. Backend manager authorization and an explicit reasoned decision resume the graph; receiving remains separate. Tests prove replay, rejection, crash-after-commit recovery, cancellation-after-checkpoint recovery and cross-run admission limits without duplicate orders. No external supplier submission is claimed.
- Native generation diagnosis: `gemini-3.1-flash-lite` metadata succeeds; one stable-v1 completion and a native JSON stream succeeded. The latter delivered **three model records over nine network chunks**. SDK SSE and several instruction/tool-bearing attempts returned real provider 503/high-demand responses. Stable API schemas now use supported `parameters`/`response_schema`, and the native JSON stream is incrementally decoded into application SSE, with no fake typing timers. Tests cover fragmented UTF-8, malformed/truncated arrays, early record delivery, rate limits and error objects embedded in HTTP-200 streams.
- `6f29aaf` adds private knowledge management/upload/search/source excerpts, agent proposal/trace/decision/resume UI, actual conversation citation/tool cards, and a labelled reusable component lab (including display-only diff/specification examples). Server deadlines are reflected in upload/search/workflow client deadlines. UI restrictions supplement backend enforcement.
- `adffd0d` adds a standard authenticated read-only MCP facade (four fixed tools), **10 passing tests including real stdio initialization/discovery**, CI, multistage non-root container images, streaming nginx, local preview Compose and Cloud Run/Cloud SQL/Secret Manager preparation. Both final images build. The backend image returns real health/readiness against the existing demo PostgreSQL in an ephemeral container; that container was stopped/removed. Nginx validation and all four YAML parses pass. CI has not executed remotely; cloud resources are not deployed.

### Final local checks

- Backend full latest run: **132 passed, one optional readiness probe skipped** because its separate opt-in variable was unset. Immediately ran that probe with `RETAILOPS_TEST_DATABASE_URL`: **one passed**. Earlier complete run before the eight native-stream regressions: **125 passed with no skips**. All business/RAG/checkpoint integration fixtures used real isolated PostgreSQL schemas. Final Ruff lint and format checks pass (84 Python files).
- Frontend final format/lint/typecheck, **45 tests across 11 files**, and production build pass. Maximum lazy chunk is about 357.54 kB before compression; this is a build size, not a load benchmark.
- Full cost-free browser regression: **12 passed across desktop/mobile**, covering actual reporting, stock/PO transactions, analyst denial, durable agent proposal/approval with unchanged inventory, replay, ownership and explicit unavailable-provider states.
- Installed backend audit: **no known vulnerabilities** (editable application excluded); frontend audit: **zero vulnerabilities**. `pip check` passes. Staged whitespace and secret-pattern scans pass before milestone commits; local `.env`, keys, dependency folders, builds and browser traces are not committed.

### Final live browser result and remaining boundary

- Local API was initially started in a network-restricted sandbox; browser embedding failures there were distinguished from successful network-enabled SDK checks. Restarted the API with network access. The final gated browser run **successfully searched the manager's private policies and displayed a matching persisted source excerpt on desktop/mobile**.
- Its single subsequent chat turn ended with **`ai_unavailable`**. No completed grounded answer, successful chat tool trace or successful replay is claimed. The script stopped without retry. `docs/verification/live-browser.json` and honest error screenshots preserve the result; prior restricted-network evidence is separately labelled. No further paid verification runs were made after the final allocation.
- Local configuration now enables Gemini and RAG with `gemini-3.1-flash-lite`, stable v1/native JSON, a 1,024-token output cap and zero retries. The key was preserved without display and remains ignored. PostgreSQL, API and frontend are available locally.
- Source implementation for the remaining requested modules is present and tested. **The complete grounded Gemini chat demonstration is not yet verified**, due to the final provider failure; the project must not be described as fully working end to end or production deployed. Remote CI execution, cloud provisioning/deployment and additional paid verification remain separate actions requiring authorization.

## 2026-10-20 - Resumed completion and successful grounded Gemini demonstration

- Resumed the same feature branch and preserved the existing changes. User explicitly authorized a new maximum of six generation and four embedding requests, with no retries and at most 1,024 output tokens per generation. Used **four generation and four embedding requests**; subsequent source/UI/replay checks made no new paid calls.
- Live document search succeeded. The first model turn now reached Gemini but failed with `ai_invalid_output`. Safe metadata inspection identified a concrete compatibility bug: REST responses include additive `usageMetadata.serviceTier`, which SDK 1.75 rejects as an extra field. The adapter now ignores additive wire metadata while validating consumed values; strict application tool-argument validation remains intact. Added a regression containing a real response shape, an argument-free sales function call and the new metadata.
- The corrected real turn **completed successfully**: Gemini selected `get_sales_summary`, read the real database report, returned a sourced answer and saved two messages, three citations and one completed tool trace. The two generation requests reported **2,799 input + 105 output = 2,904 total tokens**. Server duration was **7,172 ms for this single run**, not a performance benchmark or measured monetary cost.
- Verified answer revenue against the authenticated SQL dashboard and citation excerpts against the owner's actual source documents. The answer correctly states Monday shelf counting and avoids presenting stockout correlation as proven sales causation. Sales tools now also return explicit UTC reporting dates/day counts, with a real PostgreSQL regression, and the prompt requires the reporting period to be stated.
- Fixed a verification-harness mistake: raw Markdown cannot be matched literally against rendered text. The completed answer was then reopened without new model/embedding calls; real clipboard copying (with platform line-ending normalization), desktop/mobile rendering and saved-request replay pass. Replay preserves the same answer/message ID and creates no extra messages. Latest combined evidence is `docs/verification/live-browser.json`; detailed zero-paid-call recovery is `live-saved-answer.json`. Historical failures remain separately labelled.
- Recaptured the existing approved workflow using read-only requests after clearing focus/scroll state; no new order or workflow/model action was performed. Real generated-answer screenshots are `assistant-live-desktop.png` and `assistant-live-mobile.png`; fixture/error screenshots are not represented as model output.
- Full backend suite after the metadata fix: **134 passed with no skips**, Ruff lint/format pass. The additional reporting-period regression also passes; the final full regression result is recorded in the closing verification entry below. Frontend source remains at **45 passing unit tests**, strict types, lint, formatting and production build; **12 real desktop/mobile browser regression cases** previously passed. Fresh script syntax/format checks and read-only live UI checks pass.
- Local retail, document retrieval, grounded Gemini conversations and checkpointed explicit human approval are now verified. CI/container/deployment/MCP sources and interview guides are complete locally. **No remote push, GitHub-hosted CI execution, paid cloud provisioning or production deployment was performed.** Those remain external release operations, not claims of this local demonstration.

### Closing verification

- Final full backend regression, including the additional reporting-period test: **135 passed, zero skips**. Ruff lint and formatting pass (84 Python files). The final backend image builds and passes an isolated metadata-parser smoke inside the production image without network/model calls.
- Frontend remains at **45 passing tests**, strict typecheck, lint and production build; final formatting/script syntax checks pass. **12 real desktop/mobile regression cases** plus the opt-in generated-answer/source checks and zero-paid-call saved-answer/replay checks pass as described above.
- Both container builds and local readiness were verified; CI/cloud templates are ready for a separately authorized release. All implementation, browser evidence and current interview/security/architecture docs are captured in scoped local commits. Local environment files and credentials remain ignored.

## 2026-10-20 - Authorized deployment preparation on free hosting

- User authorized deployment and identified Google Cloud project `gen-lang-client-0064505263`. Chrome confirmed access as the requested Google account. Linked the explicitly approved existing billing account. No paid GCP resources were created.
- User set a US$1 monthly budget and then selected **free hosting plans only**. Replaced the paid Cloud SQL / Cloud Run release target with Neon Free and Render Free. Google Cloud billing remains linked; it is not an expense cap and does not make Gemini usage free.
- Created Neon Free project `aged-dream-41430057` in Singapore, PostgreSQL 17, isolated `retailops_demo` database. Confirmed the database was empty, migrated it to 0005 and seeded synthetic retail records with a distinct random password. Local documents/conversations/sessions were not uploaded. Credentials remain in ignored local environment files and were not printed.
- Added an optional same-origin React static mount and a single unprivileged Docker image for Render's free 512 MB service. Known UI routes work while API/missing-file responses keep their correct status codes. Build context is restricted to source inputs (about 743 kB in the verified build); secrets and dependency directories are excluded.
- Combined image builds. Targeted routing/health checks: **11 passed**. Real combined-container checks against Neon pass for HTML routes, liveness/readiness, unauthenticated inventory denial, login and the authenticated dashboard. Observed idle memory was about 135 MiB under a 512 MiB limit; this is not a load benchmark. An initial cold database readiness response was 503; a subsequent direct connection and repeated readiness/login checks passed.
- Signed into Render through the explicitly approved Google basic-profile flow. Used the public source repository, without expanding GitHub repository permissions. Prepared Singapore / Docker / Free compute and the exact allowed host. Public service creation and secret upload await the concrete final browser confirmation. Gemini is disabled for the initial free-hosted release; no deployment verification model/embedding calls have been made.
- Complete backend regression after the deployment changes: **136 passed, zero skips** in 137 seconds against isolated local PostgreSQL test schemas. Ruff lint and formatting pass (86 Python files). The combined Docker build also runs the actual strict TypeScript and Vite production build successfully.
- User explicitly approved storing the new Neon DSN in Render and publishing the password-protected app with Gemini disabled. Created Render **Free** service `srv-dbbeq1m7bikc738aclig`, Singapore, manual deployments, exact host and `/api/v1/ready` health check. First deployment `dep-dbbeq267bikc738acmr0` is live from commit `0647d95` at **https://retailops-ai-bhargavi.onrender.com**.
- Hosted verification: **55 actual HTTPS checks pass**, including real database readiness, HTML/deep links, expected 404s, anonymous denial, manager/analyst/admin logins, database-backed retail/private list endpoints, analyst stock-write denial, logout and revoked-token denial. Zero model/embedding requests. Evidence: `docs/verification/deployment.json`. Actual manager Chrome sign-in and rendered dashboard also pass.
- [GitHub Actions run 39369509186](https://github.com/BhargaviAlimilli/RetailOps-AI/actions/runs/39369509186) completed successfully for `0647d95`: backend, frontend (45 tests), all container builds, Git history secret scan (no leaks), and browser regression jobs. Platform deprecation notices are not failed checks. Corrected remaining local-only UI labels for the hosted demonstration; credentials stay private in ignored environment files.
- Final application release `4a0244a` is live through Render deployment `dep-dbbetmjrjlhs73e1dktg`. Fresh **55 HTTPS checks pass** for that exact release, and its public HTML references the corrected UI bundle. A fresh manager Chrome login shows the real dashboard and accurate demo labels. Final local frontend formatting/lint/typecheck, **45 tests**, and build pass.
- [GitHub Actions run 39370145943](https://github.com/BhargaviAlimilli/RetailOps-AI/actions/runs/39370145943) passed **all five jobs** for the final application release (3m37s), including browser regressions and secret scanning. Runtime application source is unchanged by the closing documentation/evidence commit. Free-hosted release is complete with Gemini/RAG deliberately disabled under the user's approved configuration. No paid cloud instance, paid hosting plan, external supplier order or deployment-time model/embedding call was created.


## 2026-10-20 - Hosted Gemini/RAG activation and full synthetic scenario

- User explicitly approved storing the existing Gemini key in Render, up to four generation requests (1,024 output tokens each, no retries) and six short-text embedding requests. Credentials remain server-only and ignored locally. No runtime source changed.
- First ingestion and a bounded independent embedding diagnostic both failed with HTTP 402: Google required prepaid credits on the billing-linked project. Official documentation confirmed a US$5 minimum and an option to unlink billing for the free tier. The user explicitly approved unlinking only RetailOps project `gen-lang-client-0064505263`; Cloud Console confirmed success. Other projects, Render and Neon were unchanged. No credits were purchased.
- Corrected the daily ingestion allowance from one to two after the initial failed attempt. A settings edit did not persist on the first save; the corrected value was explicitly filled and deployed as `dep-dbbl7mtg1s2s739bovd0`, unchanged application commit `4a0244a`. An admission-denied attempt made no embedding request.
- Actual Chrome manager scenario passed: fictional text policy indexed as one ready chunk, source search returned the real excerpt, Gemini selected `get_sales_summary`, streamed a completed answer citing Monday shelf counts, and correctly avoided causal stockout claims. SQL dashboard confirms **764,400.00 INR** revenue for the 28 completed UTC days September 22?October 19. Saved answer reports 1,947 input and 121 output tokens across its two model rounds (2,068 total); this is usage evidence, not a measured cost.
- Cited workflow prepared an internal purchase proposal for **30 units / 1,950.00 INR**, persisted the human approval checkpoint, and recorded the manager's explicit review reason and confirmation in Chrome. Approval did not change stock. Separate authorized demo receiving added exactly 30 units; idempotent receipt replay added none. No external supplier order was sent.
- **22 real HTTPS assertions pass**, including answer/database agreement, actual source references, saved answer replay with identical message ID and no extra messages, workflow resume without a duplicate order, audited receiving, cross-user private-resource 404s and analyst write 403s. Reopening the saved conversation in Chrome also succeeds without generating another answer. A harness step-name capitalization mismatch was corrected against the real API before the complete pass.
- Total bounded provider attempts: **2 generation requests; 4 successful embedding requests and 2 rejected embedding requests; zero automatic retries**. No additional provider calls were used for replay or access checks. Google free-tier quotas/data terms and Render/Neon free-plan limits apply. The manager's daily ingestion/retrieval allowances were consumed by verification.
- Evidence: `docs/verification/hosted-ai-e2e.json`. Existing 136 backend tests, 45 frontend tests and five successful CI jobs remain prior application-source verification; they were not rerun or represented as new checks for this configuration/documentation-only update.
