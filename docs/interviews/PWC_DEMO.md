# PwC demo walkthrough — 12–15 minutes

This is a rehearsal guide, not a claim that every live external integration has been verified. Use only the synthetic demo workspace. Before presenting, check `docs/IMPLEMENTATION_PROGRESS.md` for the latest actual test results and outstanding verification. Do not label mocked SDK tests as live Gemini output, local containers as deployed services, or internal approval as an external supplier submission.

## Preparation

Start PostgreSQL, apply approved **demo** migrations, load the safe synthetic seed, and start API/frontend using the README. Confirm database readiness and sign in as manager. Keep a separate analyst session for permission checks. Open the repository in an editor and have the test output available. Do not display `.env`, tokens, passwords, provider debug responses, or private documents during screen sharing.

Fresh setups default to disabled AI. This workspace was explicitly authorized and locally enabled. Live embedding retrieval and the full tool-bearing Gemini answer now pass: revenue matches the database, source excerpts match owned documents, and desktop/mobile display, copying and saved replay were verified. Earlier provider failures and the additive-metadata parsing fix remain recorded in the progress log. New live calls require an authorized budget; replaying the existing saved answer does not generate again.

## Walkthrough

| Time | Demonstration | Technical point |
|---|---|---|
| 0:00–1:30 | Sign in; filter dashboard by store, dates, category; compare revenue with the API response | Metrics originate in SQLAlchemy/PostgreSQL and preserve Decimal money; React charts visualize API data |
| 1:30–3:00 | Inspect product search/pagination, sales ledger, inventory available/reserved quantities; record a small documented synthetic adjustment | TanStack Query server state, reusable tables/dialogs, Zod boundaries and audited transactions |
| 3:00–4:00 | Show analyst access and a forbidden write response | Backend roles protect direct API calls; hiding a button is only presentation |
| 4:00–6:00 | Open AI Companion; create a private conversation; with an authorized verified provider, send a question and stop/recover a reply | Authenticated fetch SSE, partial persistence, stable request IDs, cancellation and safe Markdown |
| 6:00–7:30 | Ask for actual sales/stock evidence; inspect validated tool cards and evidence | Allowlisted functions receive typed arguments; the model has no arbitrary SQL or execution tool |
| 7:30–9:00 | Upload a clearly synthetic text/Markdown policy; search; inspect exact supporting excerpts and source preview | Owned chunks, configured embeddings, lexical/vector ranking, RRF and grounded citations; ingestion/search can incur authorized provider cost |
| 9:00–11:00 | Start a replenishment workflow for a low-stock product and associated supplier; review proposal; explicitly approve/reject; inspect order audit | Deterministic demand/pack/minimum calculation, durable LangGraph checkpoint/interrupt, backend-authorized transition and idempotency |
| 11:00–12:00 | Receive an approved synthetic order and inspect stock movement | Receiving is a separate internal action; all line updates and order status commit atomically |
| 12:00–14:00 | Show source layering, focused tests, MCP tool discovery and CI definition | Thin FastAPI routes; service transactions; typed repository reads; real PostgreSQL tests; standard read-only MCP integration |
| 14:00–15:00 | Explain Cloud Run/Cloud SQL/Secret Manager preparations and remaining limits | Deployment templates require review/approval; no paid infrastructure or live production deployment is claimed |

The document, grounded chat and checkpointed approval paths have passed the recorded local checks. Rehearse before presenting because external provider availability can change. The graph performs a bounded deterministic workflow; do not call it an unrestricted autonomous or multi-agent purchasing system.

## Source tour

- `frontend/src/features/retail/` demonstrates feature composition, query keys and validated forms; `components/ui/DataTable.tsx` provides shared tabular behavior.
- `frontend/src/components/ai/` separates message rendering, streaming status, composer, citations and tool/proposal presentation.
- `frontend/src/features/assistant/sse.ts` handles fragmented UTF-8/framing, duplicate IDs and cancellation.
- `backend/app/api/v1/` defines authenticated contracts. Services own transactions; repositories construct typed database queries.
- `backend/app/ai/gemini.py` adapts the official SDK with bounded generation and explicit automatic-tool-execution disablement.
- `backend/app/rag/` handles ingestion and retrieval. Discuss the actual ranking implementation rather than claiming benchmark superiority.
- `backend/app/services/agents.py` defines the durable interrupt/resume workflow; purchasing services remain the authority for costs and transitions.
- `backend/app/mcp_server.py` exposes only four authenticated read tools through a standard stdio MCP server.

## Failure rehearsal

Show one useful failure deliberately: invalid quantity, unavailable AI, a read-only write rejection, a conflicting idempotency key, or a retrieval result with no evidence. Explain why an empty/error state is more useful than invented certainty. Stockouts can correlate with falling sales; neither the dashboard nor the model establishes causation from that correlation.

If a provider or deployment dependency fails, continue with verified retail workflows and inspect real tests/source. State the missing external verification clearly. The complete requested AI journey is not interview-ready until an actual authorized streamed model reply, retrieval/citations, tool evidence and approval flow have been rehearsed end to end.
