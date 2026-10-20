import asyncio
import json

import httpx
import pytest

from app.ai.gemini import GeminiProvider
from app.ai.json_stream import records
from app.ai.provider import AIMessage, ProviderError
from app.core.config import Settings


async def bytes_of(data):
    for byte in data:
        yield bytes([byte])


def test_fragmented_utf8_json_stream_yields_each_record():
    async def run():
        body = json.dumps([{"text": "Café"}, {"text": "Second"}], ensure_ascii=False).encode()
        assert [item async for item in records(bytes_of(body))] == [
            {"text": "Café"},
            {"text": "Second"},
        ]

    asyncio.run(run())


def test_additive_rest_metadata_does_not_discard_valid_function_calls():
    response = [
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {"name": "get_sales_summary"},
                                "thoughtSignature": "dGVzdA==",
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 745,
                "candidatesTokenCount": 12,
                "totalTokenCount": 757,
                "serviceTier": "standard",
            },
        },
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": ""}]}}]},
    ]

    def factory(**kwargs):
        return httpx.AsyncClient(
            **kwargs,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
        )

    async def run():
        provider = GeminiProvider(
            Settings(
                _env_file=None,
                ai_provider="gemini",
                ai_model="gemini-test-model",
                gemini_api_key="fictional-key",
            ),
            stream_client_factory=factory,
        )
        chunks = [
            chunk
            async for chunk in provider.stream(
                [AIMessage(role="user", content="Revenue?")], system="Use validated tools"
            )
        ]
        assert chunks[0].kind == "tool_call"
        assert chunks[0].tool_call.name == "get_sales_summary"
        assert chunks[0].tool_call.arguments == {}
        assert chunks[1].usage.total_tokens == 757
        assert chunks[-1].finish_reason == "STOP"

    asyncio.run(run())


@pytest.mark.parametrize(
    "body", [b'{"bad":1}', b'[{"a":1}', b'[{"a":1},]', b"[1]", b"[]x", b'["\xff"]']
)
def test_malformed_json_stream_rejected(body):
    async def run():
        with pytest.raises(ProviderError):
            _ = [item async for item in records(bytes_of(body))]

    asyncio.run(run())


def test_native_stream_transport_yields_before_response_finishes_and_sanitizes_errors():
    consumed = []

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            consumed.append(1)
            yield b'[{"candidates":[{"content":{"parts":[{"text":"First"}]}}]}'
            consumed.append(2)
            yield (
                b',{"candidates":[{"content":{"parts":[{"text":"Second"}]},'
                b'"finishReason":"STOP"}]}]'
            )

    def handle(request):
        assert "alt=sse" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "fictional-key"
        return httpx.Response(200, stream=Body())

    def factory(**kwargs):
        return httpx.AsyncClient(**kwargs, transport=httpx.MockTransport(handle))

    async def run():
        provider = GeminiProvider(
            Settings(
                _env_file=None,
                ai_provider="gemini",
                ai_model="gemini-test-model",
                gemini_api_key="fictional-key",
            ),
            stream_client_factory=factory,
        )
        stream = provider.stream([AIMessage(role="user", content="Question")], system="System")
        first = await anext(stream)
        assert first.text == "First" and consumed == [1]
        remaining = [chunk async for chunk in stream]
        assert remaining[0].text == "Second"

        def bad_factory(**kwargs):
            return httpx.AsyncClient(
                **kwargs,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(429, text="private transport detail")
                ),
            )

        bad = GeminiProvider(
            provider.settings.model_copy(update={"ai_max_retries": 0}),
            stream_client_factory=bad_factory,
        )
        with pytest.raises(ProviderError) as error:
            _ = [
                chunk
                async for chunk in bad.stream([AIMessage(role="user", content="Q")], system="S")
            ]
        assert error.value.code == "ai_rate_limited"
        assert "private transport detail" not in str(error.value)

        def embedded_factory(**kwargs):
            return httpx.AsyncClient(
                **kwargs,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json=[{"error": {"code": 503, "message": "private upstream detail"}}]
                    )
                ),
            )

        embedded = GeminiProvider(bad.settings, stream_client_factory=embedded_factory)
        with pytest.raises(ProviderError) as error:
            _ = [
                chunk
                async for chunk in embedded.stream(
                    [AIMessage(role="user", content="Q")], system="S"
                )
            ]
        assert error.value.code == "ai_unavailable"
        assert "private upstream detail" not in str(error.value)

    asyncio.run(run())
