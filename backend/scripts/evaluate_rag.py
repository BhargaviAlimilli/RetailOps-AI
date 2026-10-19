"""Reproducible offline keyword/vector/hybrid ranking comparison on fictional fixtures."""

import argparse
import json
import uuid
from pathlib import Path

from app.rag.evaluation import RetrievalCase, evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    directory = Path(__file__).parents[1] / "fixtures" / "data" / "documents"
    corpus = {
        uuid.uuid5(uuid.NAMESPACE_URL, f"retailops-fixture:{path.name}"): path.read_text(
            encoding="utf-8"
        )
        for path in sorted(directory.glob("*.md"))
    }
    keys = {
        path.name: uuid.uuid5(uuid.NAMESPACE_URL, f"retailops-fixture:{path.name}")
        for path in directory.glob("*.md")
    }
    cases = []
    for case in json.loads((directory / "retrieval-cases.json").read_text()):
        # Deliberately simple mock semantic oracle; this measures plumbing, not real-model quality.
        query = case["query"].casefold()
        name = (
            "stock-counting.md"
            if "count" in query
            else "supplier-policy.md"
            if "supplier" in query
            else "returns-policy.md"
            if "refund" in query
            else None
        )
        cases.append(
            RetrievalCase(
                case["query"],
                keys[case["expected"]] if case["expected"] else None,
                [keys[name]] if name else [],
            )
        )
    report = {
        "mode": "offline_mock_vectors",
        "model_calls": 0,
        "limitations": (
            "Four synthetic queries and deterministic mock semantic rankings verify retrieval "
            "plumbing; these metrics do not establish live embedding quality "
            "or answer faithfulness."
        ),
        "documents": len(corpus),
        "metrics": evaluate(corpus, cases),
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
