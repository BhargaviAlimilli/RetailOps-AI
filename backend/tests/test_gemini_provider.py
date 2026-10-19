import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import errors, types
from pydantic import BaseModel

from app.ai.gemini import GeminiProvider
from app.ai.provider import AIMessage, ProviderError, ToolDefinition
from app.core.config import Settings


def configured(**overrides):
    return Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="gemini-test-model",
        gemini_api_key="fictional-not-a-real-api-key",
        gemini_stream_transport="sse",
        **overrides,
    )


def response(text="hello", *, call=False):
    part = (
        types.Part(function_call=types.FunctionCall(name="lookup", args={"id": 7}))
        if call
        else types.Part(text=text)
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(parts=[part]), finish_reason="STOP")],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=5, candidates_token_count=2, total_token_count=7
        ),
    )


class Stream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = next(self.chunks, None)
        if value is None:
            raise StopAsyncIteration
        if isinstance(value, Exception):
            raise value
        return value

    async def aclose(self):
        self.closed = True


def provider_with_sdk(settings=None):
    models = SimpleNamespace(
        generate_content=AsyncMock(return_value=response()),
        generate_content_stream=AsyncMock(return_value=Stream([response()])),
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models, aclose=AsyncMock()))
    factory = MagicMock(return_value=client)
    return GeminiProvider(settings or configured(), client_factory=factory), client, factory


def test_disabled_never_constructs_client():
    provider, _, factory = provider_with_sdk(Settings(_env_file=None, ai_provider="disabled"))
    with pytest.raises(ProviderError, match="not configured"):
        asyncio.run(provider.complete([AIMessage(role="user", content="hello")], system="system"))
    factory.assert_not_called()


def test_completion_tools_usage_and_explicit_sdk_configuration():
    provider, client, factory = provider_with_sdk()
    client.aio.models.generate_content.return_value = response(call=True)
    result = asyncio.run(
        provider.complete(
            [AIMessage(role="user", content="hello")],
            system="no business data",
            tools=[
                ToolDefinition(
                    name="lookup", description="Read only", parameters={"type": "object"}
                )
            ],
        )
    )
    assert result.tool_calls[0].arguments == {"id": 7}
    assert result.usage.total_tokens == 7
    config = client.aio.models.generate_content.call_args.kwargs["config"]
    assert config.automatic_function_calling.disable
    assert config.max_output_tokens == 1024
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert factory.call_args.kwargs["http_options"].api_version == "v1"
    assert client.aio.models.generate_content.call_args.kwargs["model"] == "gemini-test-model"
    client.aio.aclose.assert_awaited_once()


def test_structured_output_is_validated():
    class Answer(BaseModel):
        count: int

    provider, client, _ = provider_with_sdk()
    client.aio.models.generate_content.return_value = response('{"count":3}')
    assert asyncio.run(provider.structured([], system="system", schema=Answer)).count == 3
    client.aio.models.generate_content.return_value = response('{"count":"not-an-integer"}')
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.structured([], system="system", schema=Answer))
    assert error.value.code == "ai_invalid_output"


def test_stream_retries_only_before_first_token_and_closes(monkeypatch):
    async def run():
        provider, client, _ = provider_with_sdk()
        first = Stream([errors.APIError(503, {"error": {"message": "fake-private-key"}})])
        second = Stream(
            [response("partial"), errors.APIError(503, {"error": {"message": "fake-private-key"}})]
        )
        client.aio.models.generate_content_stream.side_effect = [first, second]
        monkeypatch.setattr("app.ai.gemini.asyncio.sleep", AsyncMock())
        events = []
        with pytest.raises(ProviderError) as error:
            async for event in provider.stream([], system="system"):
                events.append(event)
        assert error.value.code == "ai_unavailable"
        assert "fake-private" not in str(error.value)
        assert [event.text for event in events if event.kind == "text"] == ["partial"]
        assert client.aio.models.generate_content_stream.await_count == 2
        assert first.closed and second.closed
        client.aio.aclose.assert_awaited_once()

    asyncio.run(run())


def test_stream_usage_tool_event_and_consumer_close():
    async def run():
        provider, client, _ = provider_with_sdk()
        stream = Stream([response(call=True), response("hello")])
        client.aio.models.generate_content_stream.return_value = stream
        iterator = provider.stream([], system="system")
        event = await anext(iterator)
        assert event.kind == "tool_call" and event.tool_call.name == "lookup"
        await iterator.aclose()
        assert stream.closed
        client.aio.aclose.assert_awaited_once()

    asyncio.run(run())


def test_deadline_normalizes_error_and_closes_without_retry():
    async def run():
        provider, client, _ = provider_with_sdk(configured(ai_timeout_seconds=0.001))

        async def blocked(**kwargs):
            await asyncio.Event().wait()

        client.aio.models.generate_content.side_effect = blocked
        with pytest.raises(ProviderError) as error:
            await provider.complete([], system="system")
        assert error.value.code == "ai_timeout"
        client.aio.models.generate_content.assert_awaited_once()
        client.aio.aclose.assert_awaited_once()

    asyncio.run(run())


def test_constructor_failure_and_malformed_completion_are_sanitized():
    provider, client, factory = provider_with_sdk()
    factory.side_effect = ValueError("fictional-private-constructor-key")
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.complete([], system="system"))
    assert error.value.code == "ai_unavailable"
    assert "fictional-private" not in str(error.value)
    factory.side_effect = None
    client.aio.models.generate_content.return_value = SimpleNamespace(candidates="malformed")
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.complete([], system="system"))
    assert error.value.code == "ai_invalid_output"


def test_stream_propagates_token_limit_finish_reason():
    async def run():
        provider, client, _ = provider_with_sdk()
        chunk = response("truncated")
        chunk.candidates[0].finish_reason = types.FinishReason.MAX_TOKENS
        client.aio.models.generate_content_stream.return_value = Stream([chunk])
        events = [event async for event in provider.stream([], system="system")]
        assert events[-1].kind == "end"
        assert events[-1].finish_reason == "MAX_TOKENS"

    asyncio.run(run())


@pytest.mark.parametrize("model", [" ", "not-a-gemini-model", "fictional-private-api-key"])
def test_model_identifier_is_validated_without_secret_echo(model):
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, ai_model=model)
    assert "input_value" not in str(error.value)
    assert (
        Settings(_env_file=None, ai_model=" models/gemini-test-model ").ai_model
        == "models/gemini-test-model"
    )


def test_real_sdk_serializes_stable_stream_tools_without_beta_fields():
    import json

    import httpx
    from google import genai

    from app.ai.tools import definitions

    async def run():
        requests = []

        def handle(request):
            requests.append(request)
            assert request.url.path.startswith("/v1/models/")
            payload = json.loads(request.content)
            assert len(payload["tools"][0]["functionDeclarations"]) == 8
            assert "parametersJsonSchema" not in request.content.decode()
            assert "parameters_json_schema" not in request.content.decode()
            frame = {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Safe response"}], "role": "model"},
                        "finishReason": "STOP",
                    }
                ]
            }
            return httpx.Response(
                200,
                text="data: " + json.dumps(frame) + "\n\n",
                headers={"content-type": "text/event-stream"},
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

        def factory(**kwargs):
            kwargs["http_options"] = kwargs["http_options"].model_copy(
                update={"httpx_async_client": http_client}
            )
            return genai.Client(**kwargs)

        provider = GeminiProvider(configured(), client_factory=factory)
        chunks = [
            chunk
            async for chunk in provider.stream(
                [AIMessage(role="user", content="Explain stock")],
                system="Be accurate",
                tools=definitions(),
            )
        ]
        assert len(requests) == 1
        assert chunks[0].text == "Safe response"

    asyncio.run(run())
