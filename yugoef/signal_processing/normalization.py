from __future__ import annotations


def minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]
