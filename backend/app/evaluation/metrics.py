"""Retrieval metrics over control ids. relevant = expected_control_ids."""


def hit_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return float(any(r in relevant for r in ranked[:k]))


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(relevant & set(ranked[:k])) / len(relevant) if relevant else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, r in enumerate(ranked, start=1):
        if r in relevant:
            return 1.0 / i
    return 0.0
