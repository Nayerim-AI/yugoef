from __future__ import annotations

import math


def phase_unwrap(values: list[float]) -> list[float]:
    if not values:
        return []
    out = [values[0]]
    offset = 0.0
    previous = values[0]
    for value in values[1:]:
        delta = value - previous
        if delta > math.pi:
            offset -= 2 * math.pi
        elif delta < -math.pi:
            offset += 2 * math.pi
        out.append(value + offset)
        previous = value
    return out
