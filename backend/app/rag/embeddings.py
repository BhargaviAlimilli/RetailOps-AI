import asyncio
import math
from collections.abc import Callable
from threading import BoundedSemaphore
from typing import Literal, Protocol

from google import genai
from google.genai import types

from app.ai.gemini import close_upstream, normalize_error
from app.ai.provider import ProviderError
from app.core.config import Settings

EmbeddingTask = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
embedding_slots = BoundedSemaphore(4)


class Embeddings(Protocol):
    def ensure_available(self) -> None: ...
    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> list[list[float]]: ...


class GeminiEmbeddings:
    def __init__(self, settings: Settings, *, client_factory: Callable | None = None):
        self.settings = settings
        self.client_factory = client_factory or genai.Client

    def ensure_available(self) -> None:
        if (
            not self.settings.rag_enabled
            or self.settings.gemini_api_key is None
            or not self.settings.gemini_api_key.get_secret_value().strip()
        ):
            raise ProviderError("ai_disabled")

    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> list[list[float]]:
        self.ensure_available()
        if (
            not texts
            or len(texts) > self.settings.rag_max_chunks_per_document
            or any(not text or len(text) > 2000 for text in texts)
        ):
            raise ValueError("Embedding input exceeds configured bounds")
        client = None
        if not embedding_slots.acquire(blocking=False):
            raise ProviderError("ai_rate_limited")
        try:
            client = self.client_factory(
                vertexai=False,
                api_key=self.settings.gemini_api_key.get_secret_value(),
                http_options=types.HttpOptions(
                    timeout=int(self.settings.rag_timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            vectors = []
            async with asyncio.timeout(self.settings.rag_timeout_seconds):
                for start in range(0, len(texts), self.settings.rag_embedding_batch_size):
                    batch = texts[start : start + self.settings.rag_embedding_batch_size]
                    response = await client.aio.models.embed_content(
                        model=self.settings.gemini_embedding_model,
                        contents=batch,
                        config=types.EmbedContentConfig(task_type=task, output_dimensionality=768),
                    )
                    embeddings = response.embeddings or []
                    if len(embeddings) != len(batch):
                        raise ProviderError("ai_invalid_output")
                    for embedding in embeddings:
                        values = embedding.values or []
                        if len(values) != 768 or any(not math.isfinite(value) for value in values):
                            raise ProviderError("ai_invalid_output")
                        norm = math.sqrt(sum(value * value for value in values))
                        if norm == 0 or not math.isfinite(norm):
                            raise ProviderError("ai_invalid_output")
                        vectors.append([value / norm for value in values])
            return vectors
        except ProviderError:
            raise
        except Exception as error:
            raise normalize_error(error) from None
        finally:
            if client is not None:
                await close_upstream(client.aio)
            embedding_slots.release()
