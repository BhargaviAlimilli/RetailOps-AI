"""Compute retrieval metrics from supplied rankings; never call a model."""

import uuid
from dataclasses import dataclass

from app.rag.ranking import bm25, rank


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    expected: uuid.UUID | None
    semantic_ranking: list[uuid.UUID]


def evaluate(
    corpus: dict[uuid.UUID, str], cases: list[RetrievalCase]
) -> dict[str, dict[str, float]]:
    methods = ("bm25", "vector", "hybrid", "hybrid_reranked")
    totals = {
        name: {"combined": 0.0, "mrr": 0.0, "hit1": 0.0, "recall5": 0.0, "abstention": 0.0}
        for name in methods
    }
    answerable = sum(case.expected is not None for case in cases)
    unanswerable = len(cases) - answerable
    for case in cases:
        rankings = {
            "bm25": bm25(case.query, corpus),
            "vector": case.semantic_ranking,
            "hybrid": [
                key for key, _ in rank(case.query, corpus, case.semantic_ranking, rerank=False)
            ],
            "hybrid_reranked": [
                key for key, _ in rank(case.query, corpus, case.semantic_ranking, rerank=True)
            ],
        }
        for name, ranking in rankings.items():
            if case.expected is None:
                totals[name]["combined"] += float(not ranking)
                totals[name]["abstention"] += float(not ranking)
            elif case.expected in ranking:
                reciprocal = 1 / (ranking.index(case.expected) + 1)
                totals[name]["combined"] += reciprocal
                totals[name]["mrr"] += reciprocal
                totals[name]["hit1"] += float(ranking[0] == case.expected)
                totals[name]["recall5"] += float(case.expected in ranking[:5])
    return {
        name: {
            "mean_reciprocal_rank_or_correct_abstention": value["combined"] / max(len(cases), 1),
            "mrr_answerable": value["mrr"] / max(answerable, 1),
            "hit_at_1_answerable": value["hit1"] / max(answerable, 1),
            "recall_at_5_answerable": value["recall5"] / max(answerable, 1),
            "abstention_accuracy": value["abstention"] / max(unanswerable, 1),
            "cases": len(cases),
        }
        for name, value in totals.items()
    }
