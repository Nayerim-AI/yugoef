from __future__ import annotations

from .quality import clamp01


def presence_score(
    *,
    normalized_motion: float,
    normalized_phase_variance: float,
    normalized_amplitude_variance: float,
    active_subcarrier_ratio: float,
    motion_weight: float,
    phase_weight: float,
    amplitude_weight: float,
    active_subcarrier_weight: float,
) -> float:
    return clamp01(
        motion_weight * clamp01(normalized_motion)
        + phase_weight * clamp01(normalized_phase_variance)
        + amplitude_weight * clamp01(normalized_amplitude_variance)
        + active_subcarrier_weight * clamp01(active_subcarrier_ratio)
    )
