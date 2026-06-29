from __future__ import annotations


def moving_average(values: list[float], window: int = 3) -> list[float]:
    if window <= 1:
        return list(values)
    out: list[float] = []
    for idx in range(len(values)):
        start = max(0, idx - window + 1)
        chunk = values[start : idx + 1]
        out.append(sum(chunk) / len(chunk))
    return out
