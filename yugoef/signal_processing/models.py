from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IqSample:
    i: int
    q: int
    amplitude: float
    phase: float


@dataclass(frozen=True)
class SignalFrame:
    node_id: str
    boot_id: int
    channel: int
    antenna_index: int
    sequence: int
    uptime_ms: int
    amplitudes: list[float]
    phases: list[float]


@dataclass(frozen=True)
class SignalPipelineResult:
    frame: SignalFrame
    window_sample_count: int
    effective_sample_rate_hz: float
    missing_frames: int
    active_subcarriers: list[int]
    subcarrier_coherence: float
