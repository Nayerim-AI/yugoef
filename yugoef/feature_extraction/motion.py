from __future__ import annotations

from yugoef.signal_processing.models import SignalFrame

from .quality import clamp01


def _mean_abs_temporal_diff(rows: list[list[float]]) -> float:
    if len(rows) < 2:
        return 0.0
    total = 0.0
    count = 0
    width = min(len(row) for row in rows)
    for prev, cur in zip(rows, rows[1:]):
        for idx in range(width):
            total += abs(cur[idx] - prev[idx])
            count += 1
    return total / count if count else 0.0


def motion_energy(
    frames: list[SignalFrame],
    active_subcarriers: list[int],
    *,
    amplitude_weight: float,
    phase_weight: float,
    energy_scale: float,
) -> tuple[float, float, float]:
    if len(frames) < 2:
        return 0.0, 0.0, 0.0
    active = active_subcarriers or list(range(min(len(frame.amplitudes) for frame in frames)))
    amp_rows = [[frame.amplitudes[idx] for idx in active if idx < len(frame.amplitudes)] for frame in frames]
    phase_rows = [[frame.phases[idx] for idx in active if idx < len(frame.phases)] for frame in frames]
    amp_energy = _mean_abs_temporal_diff(amp_rows) / max(energy_scale, 1e-9)
    phase_energy = _mean_abs_temporal_diff(phase_rows) / max(energy_scale, 1e-9)
    combined = amplitude_weight * clamp01(amp_energy) + phase_weight * clamp01(phase_energy)
    return clamp01(combined), clamp01(amp_energy), clamp01(phase_energy)
