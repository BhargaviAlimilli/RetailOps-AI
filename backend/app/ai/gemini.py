"""Google Gen AI SDK adapter; no calls occur during construction or configuration."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.json_stream import records
from app.ai.provider import (
    AIMessage,
    AIResult,
    AIStreamEvent,
    ProviderError,
    Structured,
    ToolCall,
    ToolDefinition,
    Usage,
)
from app.core.config import Settings


def stable_schema(schema: dict) -> types.Schema:
    """Translate application JSON schemas to the stable API's supported Schema subset."""
    definitions = schema.get("$defs", {})

    def convert(value):
        if "$ref" in value:
            value = definitions[value["$ref"].rsplit("/", 1)[-1]]
        choices = value.get("anyOf", [])
        nullable = any(choice.get("type") == "null" for choice in choices)
        if choices:
            value = next(choice for choice in choices if choice.get("type") != "null")
        result = {"type": value.get("type", "object").upper()}
        if nullable:
            result["nullable"] = True
        for name in ("description", "enum", "required"):
            if name in value:
                result[name] = value[name]
        if "properties" in value:
            result["properties"] = {
                name: convert(item) for name, item in value["properties"].items()
            }
        if "items" in value:
            result["items"] = convert(value["items"])
        return result

    return types.Schema.model_validate(convert(schema))


async def close_upstream(resource) -> None:
    # A failed transport close must not replace sanitized errors with credential-bearing traces.
    with suppress(Exception):
        async with asyncio.timeout(2):
            await resource.aclose()


def normalize_error(error: Exception) -> ProviderError:
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return ProviderError("ai_timeout")
    if isinstance(error, errors.APIError):
        if error.code == 429:
            return ProviderError("ai_rate_limited")
        return ProviderError("ai_unavailable" if error.code >= 500 else "ai_rejected")
    return ProviderError("ai_unavailable")


class GeminiProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable | None = None,
        stream_client_factory: Callable | None = None,
    ):
        self.settings = settings
        self.client_factory = client_factory or genai.Client
        self.stream_client_factory = stream_client_factory or httpx.AsyncClient

    async def _stream_responses(self, client, messages, system, tools):
        if self.settings.gemini_stream_transport == "sse":
            upstream = await client.aio.models.generate_content_stream(
                model=self.settings.ai_model,
                contents=self._contents(messages),
                config=self._config(system, tools),
            )
            try:
                async for response in upstream:
                    yield response
            finally:
                await close_upstream(upstream)
            return
        model = self.settings.ai_model.removeprefix("models/")
        url = (
            "https://generativelanguage.googleapis.com/"
            + self.settings.gemini_api_version
            + f"/models/{model}:streamGenerateContent"
        )
        payload = {
            "contents": [
                item.model_dump(mode="json", by_alias=True, exclude_none=True)
                for item in self._contents(messages)
            ],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "maxOutputTokens": self.settings.ai_max_output_tokens,
                "candidateCount": 1,
            },
        }
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": stable_schema(tool.parameters).model_dump(
                                mode="json", by_alias=True, exclude_none=True
                            ),
                        }
                        for tool in tools
                    ]
                }
            ]
        async with self.stream_client_factory(
            timeout=httpx.Timeout(self.settings.ai_timeout_seconds, connect=5),
            follow_redirects=False,
        ) as transport:
            async with transport.stream(
                "POST",
                url,
                json=payload,
                headers={"x-goog-api-key": self.settings.gemini_api_key.get_secret_value()},
            ) as response:
                if response.status_code != 200:
                    raise errors.APIError(response.status_code, {"message": "Stream unavailable"})
                async for record in records(response.aiter_bytes()):
                    if "error" in record:
                        code = record["error"].get("code", 503)
                        raise errors.APIError(code, {"message": "Stream unavailable"})
                    try:
                        yield types.GenerateContentResponse.model_validate(record)
                    except ValidationError:
                        raise ProviderError("ai_invalid_output") from None

    def ensure_available(self) -> None:
        if (
            self.settings.ai_provider != "gemini"
            or not self.settings.ai_model
            or self.settings.gemini_api_key is None
            or not self.settings.gemini_api_key.get_secret_value().strip()
        ):
            raise ProviderError("ai_disabled")

    def _client(self):
        self.ensure_available()
        return self.client_factory(
            vertexai=False,
            api_key=self.settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(
                api_version=self.settings.gemini_api_version,
                timeout=int(self.settings.ai_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def _config(self, system, tools=None, schema=None):
        return types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.settings.ai_max_output_tokens,
            candidate_count=1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=stable_schema(tool.parameters),
                        )
                        for tool in tools
                    ]
                )
            ]
            if tools
            else None,
            response_mime_type="application/json" if schema else None,
            response_schema=stable_schema(schema.model_json_schema()) if schema else None,
        )

    @staticmethod
    def _contents(messages: list[AIMessage]) -> list[types.Content]:
        return [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part(text=message.content)],
            )
            for message in messages
        ]

    @staticmethod
    def _result(response) -> AIResult:
        text_parts, calls = [], []
        candidates = response.candidates or []
        for candidate in candidates[:1]:
            for part in (candidate.content.parts or []) if candidate.content else []:
                if part.thought:
                    continue
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    call = part.function_call
                    calls.append(ToolCall(id=call.id, name=call.name, arguments=call.args or {}))
        usage = response.usage_metadata
        return AIResult(
            text="".join(text_parts),
            tool_calls=calls,
            usage=Usage(
                input_tokens=usage.prompt_token_count or 0,
                output_tokens=usage.candidates_token_count or 0,
                total_tokens=usage.total_token_count or 0,
            )
            if usage
            else Usage(),
            finish_reason=str(candidates[0].finish_reason.value)
            if candidates and candidates[0].finish_reason
            else None,
        )

    def _retryable(self, error, attempt):
        return (
            isinstance(error, errors.APIError)
            and (error.code == 429 or 500 <= error.code < 600)
            and attempt < self.settings.ai_max_retries
        )

    async def _response(self, messages, system, tools=None, schema=None):
        self.ensure_available()
        client = None
        try:
            client = self._client()
            async with asyncio.timeout(self.settings.ai_timeout_seconds):
                for attempt in range(self.settings.ai_max_retries + 1):
                    try:
                        return await client.aio.models.generate_content(
                            model=self.settings.ai_model,
                            contents=self._contents(messages),
                            config=self._config(system, tools, schema),
                        )
                    except errors.APIError as error:
                        if not self._retryable(error, attempt):
                            raise
                        await asyncio.sleep(min(0.25 * 2**attempt, 1))
        except Exception as error:
            raise normalize_error(error) from None
        finally:
            if client is not None:
                await close_upstream(client.aio)

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResult:
        response = await self._response(messages, system, tools)
        try:
            result = self._result(response)
        except (ValidationError, AttributeError, TypeError, ValueError):
            raise ProviderError("ai_invalid_output") from None
        if not result.text and not result.tool_calls:
            raise ProviderError("ai_invalid_output")
        return result

    async def structured(self, messages, *, system, schema: type[Structured]) -> Structured:
        response = await self._response(messages, system, schema=schema)
        try:
            return schema.model_validate_json(self._result(response).text)
        except (ValidationError, AttributeError, TypeError, ValueError):
            raise ProviderError("ai_invalid_output") from None

    async def stream(
        self,
        messages: list[AIMessage],
        *,
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[AIStreamEvent]:
        self.ensure_available()
        client = None
        upstream = None
        emitted = False
        finish_reason = None
        try:
            client = self._client()
            async with asyncio.timeout(self.settings.ai_timeout_seconds):
                for attempt in range(self.settings.ai_max_retries + 1):
                    try:
                        upstream = self._stream_responses(client, messages, system, tools)
                        async for response in upstream:
                            try:
                                result = self._result(response)
                            except (ValidationError, AttributeError, TypeError, ValueError):
                                raise ProviderError("ai_invalid_output") from None
                            finish_reason = result.finish_reason or finish_reason
                            if result.text:
                                emitted = True
                                yield AIStreamEvent(kind="text", text=result.text)
                            for call in result.tool_calls:
                                emitted = True
                                yield AIStreamEvent(kind="tool_call", tool_call=call)
                            if response.usage_metadata:
                                yield AIStreamEvent(kind="usage", usage=result.usage)
                        if not emitted:
                            raise ProviderError("ai_invalid_output")
                        yield AIStreamEvent(kind="end", finish_reason=finish_reason)
                        return
                    except errors.APIError as error:
                        if emitted or not self._retryable(error, attempt):
                            raise
                        if upstream is not None:
                            await close_upstream(upstream)
                            upstream = None
                        await asyncio.sleep(min(0.25 * 2**attempt, 1))
        except ProviderError:
            raise
        except Exception as error:
            raise normalize_error(error) from None
        finally:
            if upstream is not None:
                await close_upstream(upstream)
            if client is not None:
                await close_upstream(client.aio)
