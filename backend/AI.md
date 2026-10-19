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
