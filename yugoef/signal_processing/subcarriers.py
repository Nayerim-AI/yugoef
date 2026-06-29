from __future__ import annotations

import statistics


def top_k_active_subcarriers(amplitude_rows: list[list[float]], k: int = 8) -> list[int]:
    if not amplitude_rows or k <= 0:
        return []
    width = min(len(row) for row in amplitude_rows)
    scores: list[tuple[int, float]] = []
    for idx in range(width):
        col = [row[idx] for row in amplitude_rows]
        score = statistics.pvariance(col) if len(col) > 1 else 0.0
        scores.append((idx, score))
    scores.sort(key=lambda item: (-item[1], item[0]))
    return [idx for idx, _score in scores[: min(k, width)]]


def subcarrier_coherence(amplitude_rows: list[list[float]]) -> float:
    if len(amplitude_rows) < 2:
        return 1.0
    width = min(len(row) for row in amplitude_rows)
    if width == 0:
        return 0.0
    stable = 0
    for idx in range(width):
        col = [row[idx] for row in amplitude_rows]
        mean = sum(col) / len(col)
        var = statistics.pvariance(col) if len(col) > 1 else 0.0
        if mean == 0 or (var ** 0.5) / abs(mean) < 0.5:
            stable += 1
    return max(0.0, min(1.0, stable / width))
