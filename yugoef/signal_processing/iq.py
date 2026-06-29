from __future__ import annotations

import math

from .models import IqSample


def _to_i8(value: int) -> int:
    return value - 256 if value >= 128 else value


def decode_iq(payload: bytes) -> list[IqSample]:
    if len(payload) % 2 != 0:
        raise ValueError("I/Q payload length must be even")
    samples: list[IqSample] = []
    for idx in range(0, len(payload), 2):
        i = _to_i8(payload[idx])
        q = _to_i8(payload[idx + 1])
        amplitude = math.sqrt(i * i + q * q)
        phase = math.atan2(q, i)
        if not math.isfinite(amplitude) or not math.isfinite(phase):
            raise ValueError("non-finite I/Q derived value")
        samples.append(IqSample(i=i, q=q, amplitude=amplitude, phase=phase))
    return samples
