"""Incremental JSON-array decoding for Gemini's native streaming REST transport."""

import codecs
import json

from app.ai.provider import ProviderError


async def records(chunks):
    decoder = codecs.getincrementaldecoder("utf-8")()
    parser = json.JSONDecoder()
    buffer, state, may_close = "", "open", True
    try:
        async for chunk in chunks:
            buffer += decoder.decode(chunk)
            if len(buffer) > 1_048_576:
                raise ProviderError("ai_invalid_output")
            while buffer.strip():
                buffer = buffer.lstrip()
                if state == "open":
                    if buffer[0] != "[":
                        raise ProviderError("ai_invalid_output")
                    buffer, state = buffer[1:], "value"
                elif state == "value":
                    if buffer[0] == "]" and may_close:
                        buffer, state = buffer[1:], "done"
                        continue
                    try:
                        value, end = parser.raw_decode(buffer)
                    except json.JSONDecodeError:
                        break
                    if not isinstance(value, dict):
                        raise ProviderError("ai_invalid_output")
                    yield value
                    buffer, state = buffer[end:], "separator"
                elif state == "separator":
                    if buffer[0] == ",":
                        buffer, state, may_close = buffer[1:], "value", False
                    elif buffer[0] == "]":
                        buffer, state = buffer[1:], "done"
                    else:
                        raise ProviderError("ai_invalid_output")
                else:
                    raise ProviderError("ai_invalid_output")
        buffer += decoder.decode(b"", final=True)
        if state != "done" or buffer.strip():
            raise ProviderError("ai_invalid_output")
    except UnicodeDecodeError:
        raise ProviderError("ai_invalid_output") from None
