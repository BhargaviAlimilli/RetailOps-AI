# AI backend foundation

AI defaults to disabled. Gemini requires an explicit configured model and local
secret key; no model name implies account access. The adapter uses Google Gen AI
SDK async completion/structured interfaces and native incremental JSON streaming,
disables automatic function execution and SDK retries, and applies its own bounded retry policy for 429/5xx
only before output starts. A whole-request deadline and output token limit apply.
Structured results are validated by the caller's Pydantic schema. Tool requests
are typed data and never executed by this adapter.

Provider tests substitute the SDK client and transport responses. They make no
model, network, or paid API calls. Installing an SDK does not authorize model calls.

Conversations persist user and assistant turns with an ordinal ordering and user
ownership. SSE events are named `message.started`, `message.delta`,
`message.completed`, and `message.error`; each includes sequence, conversation,
message, request IDs, and a payload. Completed answers are committed before their
completion event. A repeated request ID replays saved text without a model call;
changed input or an active duplicate receives 409. Disconnects preserve partial
text as cancelled. Expired generation leases recover interrupted replies.

History is limited to 20 completed messages and 24,000 characters. Input is limited
to 8,000 characters, output to the configured token limit plus a 32,768-character
safety bound, and conversations to 200 messages. Finish reasons, including token
limit truncation, are retained. Authenticated live turns use an allowlisted
read-only registry for sales, inventory, supplier terms, reorder calculations and
private document search. Retrieved evidence and tool results are data, never
instructions. At most four tool requests and two model rounds execute per turn;
the model cannot create/approve/receive an order or adjust stock from chat.
Dedicated citation context is preserved when large operational results are
bounded with explicit omission markers. Already retrieved documents are not
searched again by the model in the same turn.

Database-backed reservations limit active generations to two per user and four
globally, with ten logical generations per rolling minute and 100 per rolling day
per user. These defaults are configurable within bounded settings. Upstream
retries remain separately capped and may add requests to one logical generation.
These are request/resource limits, not a claim of measured monetary spend. Each
user may create at most 100 conversations, matching the bounded list response.
All generation reservations use short transactions; provider calls hold no open
database transaction. Cancellation cleanup has its own five-second deadline and
retains/consumes late cleanup tasks without logging exception details.

The default generation endpoint is stable `v1` with native JSON streaming. During
verification this model's SSE transport repeatedly returned 503 while native JSON
streaming succeeded. The adapter decodes actual UTF-8/JSON fragments and converts
them to application SSE; it never uses text animation to simulate streaming.
Stable API function/response schemas are translated from application JSON schemas;
Pydantic still validates tool inputs and structured output. Malformed arrays,
truncated UTF-8, oversized records and embedded error objects are handled safely.
The optional `sse` transport remains available for SDK compatibility checks.

Gemini may add REST metadata before the SDK declares it (observed `serviceTier`).
The native adapter ignores additive wire fields while validating consumed fields;
application tool arguments still pass their strict Pydantic contracts. This fixes
valid function calls being discarded by the SDK's extra-field rejection. A real
tool-bearing answer, source citations, persistence and saved replay are verified
in the current local demonstration; see the dated progress/evidence records.

The Replenishment workspace is a separate deterministic LangGraph workflow with
standard PostgreSQL checkpoints. It gathers actual evidence, creates/submits a
pending internal draft, interrupts, and resumes only after an explicit manager
decision. A crash after a business commit replays the same domain idempotency key.
Same-run leases and global/user admission prevent competing/excessive advancement;
bounded cancellation cleanup releases reservations. Source/document text cannot
authorize a decision. Actual approval/receiving remain domain-service transactions.

Structured logs record IDs, status, durations, token usage and tool/citation counts,
never prompt/answer/document text or credentials. Token counts are usage evidence,
not measured monetary spend. Local verification is in the progress log; provider
availability and model quality are separate from offline contract tests.
