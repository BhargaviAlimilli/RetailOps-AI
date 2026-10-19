import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    content: str
    start: int
    end: int


def normalize_text(content: str) -> str:
    return unicodedata.normalize("NFC", content.replace("\r\n", "\n").replace("\r", "\n")).strip()


def chunk_text(content: str, *, size: int = 1200, overlap: int = 160) -> list[Chunk]:
    if not 0 <= overlap < size <= 1400:
        raise ValueError("Invalid chunk bounds")
    chunks, start = [], 0
    while start < len(content):
        end = min(start + size, len(content))
        if end < len(content):
            paragraph = content.rfind("\n\n", start + size // 2, end)
            space = content.rfind(" ", start + size // 2, end)
            end = paragraph if paragraph > start else (space if space > start else end)
        if content[start:end].strip():
            chunks.append(Chunk(content[start:end], start, end))
        if end == len(content):
            break
        start = max(start + 1, end - overlap)
    return chunks


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
