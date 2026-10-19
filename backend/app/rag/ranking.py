import math
import uuid
from collections import Counter

from app.rag.chunking import tokens


def bm25(query: str, corpus: dict[uuid.UUID, str]) -> list[uuid.UUID]:
    terms = list(dict.fromkeys(tokens(query)))[:64]
    if not terms or not corpus:
        return []
    counts = {key: Counter(tokens(content)) for key, content in corpus.items()}
    lengths = {key: sum(count.values()) for key, count in counts.items()}
    average = sum(lengths.values()) / max(len(lengths), 1) or 1
    frequency = {term: sum(term in count for count in counts.values()) for term in terms}
    scores = {}
    for key, count in counts.items():
        score = 0.0
        for term in terms:
            tf = count.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(corpus) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * lengths[key] / average))
        if score > 0:
            scores[key] = score
    return sorted(scores, key=lambda key: (-scores[key], str(key)))[:30]


def fuse(lexical: list[uuid.UUID], semantic: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    scores = {}
    for ranking in (lexical, semantic):
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return scores


def rank(
    query: str, corpus: dict[uuid.UUID, str], semantic: list[uuid.UUID], *, rerank: bool = True
):
    scores = fuse(bm25(query, corpus), semantic)
    terms = set(tokens(query))

    # This is an explicit deterministic lexical-overlap reranker, not a trained cross-encoder.
    def sort_key(key):
        overlap = len(terms & set(tokens(corpus[key]))) / max(len(terms), 1)
        return (-(scores[key] + (0.01 * overlap if rerank else 0)), str(key))

    return [(key, scores[key]) for key in sorted(scores, key=sort_key)]
