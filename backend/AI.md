# AI backend foundation

AI defaults to disabled. Gemini requires an explicit configured model and local
secret key; no model name implies account access. The adapter uses Google Gen AI
SDK async completion and streaming interfaces, disables automatic function
execution and SDK retries, and applies its own bounded retry policy for 429/5xx
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
limit truncation, are retained. This stage has no operational tools or document
retrieval; the system prompt explicitly disallows claims of operational access.

Database-backed reservations limit active generations to two per user and four
globally, with ten logical generations per rolling minute and 100 per rolling day
per user. These defaults are configurable within bounded settings. Upstream
retries remain separately capped and may add requests to one logical generation.
These are request/resource limits, not a claim of measured monetary spend. Each
user may create at most 100 conversations, matching the bounded list response.
All generation reservations use short transactions; provider calls hold no open
database transaction. Cancellation cleanup has its own five-second deadline and
retains/consumes late cleanup tasks without logging exception details.
