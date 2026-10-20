# AI API contracts

All routes below require a current bearer session. Conversation, document and agent-run reads are owner-scoped; operational data is shared within the single demo organization.

| Route | Behavior |
| --- | --- |
| `GET /api/v1/ai/status` | Configuration/capability metadata only; no paid health probe |
| `GET/POST /api/v1/conversations` | List/create at most 100 private conversations |
| `GET /api/v1/conversations/{id}/messages` | Ordered saved messages, status, usage, finish reason and evidence |
| `POST /api/v1/conversations/{id}/messages` | `{content,request_id}`; authenticated fetch SSE, bounded model work |
| `GET/POST /api/v1/documents` | Private list or validated text/Markdown ingestion |
| `POST /api/v1/documents/upload` | Multipart `title`, UTF-8 `.txt`/`.md` `file`, at most 100,000 bytes |
| `POST /api/v1/documents/search` | `{query,limit}`; accessible persisted citations; embedding allowance applies |
| `GET/DELETE /api/v1/documents/{id}` | Own source preview/delete, with processing-lease checks |
| `GET/POST /api/v1/agents/runs` | Own history / manager-only deterministic replenishment preparation |
| `POST /api/v1/agents/runs/{id}/decision` | Manager action `{decision,reason,idempotency_key}`; no conversational authorization |
| `POST /api/v1/agents/runs/{id}/resume` | Manager recovery of the same saved graph; domain idempotency prevents duplicate effects |

SSE names are `message.started`, `message.delta`, `message.completed` and `message.error`. The JSON envelope carries `conversation_id`, assistant `message_id`, client `request_id`, monotonic `sequence` and `payload`. The SSE ID is `message_id:sequence`. Completion includes saved content, token usage, finish reason, citations and tool trace. Error events preserve partial text and a safe code; a 200 response header does not imply generation succeeded. Clients must read the terminal event.

A completed request ID replays saved output without generation, including when the provider is disabled. Changed content/ownership or an active duplicate returns 409. Input/history/output, concurrency and rolling allowances are independently bounded. The backend commits completion before emitting its terminal completion event; cancellation preserves recoverable partial state. Source excerpts and model text are untrusted data.

`GET /openapi.json` and `/docs` expose exact development schemas; production disables them. Ordinary unit/integration/CI tests substitute paid providers, while database behavior remains tested on PostgreSQL. Explicitly gated live scripts are separate from CI.
