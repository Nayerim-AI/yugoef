from __future__ import annotations

from dataclasses import dataclass, asdict

EXTRACTOR_VERSION = "yugoef-feature-v1"


@dataclass(frozen=True)
class FeatureConfig:
    extractor_version: str = EXTRACTOR_VERSION
    packet_loss_rate: float = 0.0
    rssi_override_dbm: int | None = None
    motion_amplitude_weight: float = 0.5
    motion_phase_weight: float = 0.5
    motion_energy_scale: float = 1.0
    presence_motion_weight: float = 0.40
    presence_phase_weight: float = 0.25
    presence_amplitude_weight: float = 0.20
    presence_active_subcarrier_weight: float = 0.15
    quality_min_rssi_dbm: int = -85
    quality_good_rssi_dbm: int = -50
    quality_min_snr_db: int = 5
    quality_good_snr_db: int = 30
    quality_max_packet_loss: float = 0.30
    quality_target_sample_rate_hz: float = 20.0

    def validate(self) -> None:
        motion_total = self.motion_amplitude_weight + self.motion_phase_weight
        presence_total = (
            self.presence_motion_weight
            + self.presence_phase_weight
            + self.presence_amplitude_weight
            + self.presence_active_subcarrier_weight
        )
        if abs(motion_total - 1.0) > 1e-6:
            raise ValueError("motion weights must sum to 1.0")
        if abs(presence_total - 1.0) > 1e-6:
            raise ValueError("presence weights must sum to 1.0")


@dataclass(frozen=True)
class CsiFeatureVector:
    node_id: str
    room_id: int
    boot_id: int
    window_id: str
    window_started_at: int
    window_ended_at: int
    sample_count: int
    effective_sample_rate_hz: float
    packet_loss_rate: float
    rssi_dbm: int
    noise_floor_dbm: int
    snr_db: int
    amplitude_mean: float
    amplitude_std: float
    amplitude_variance: float
    phase_variance: float
    phase_derivative_energy: float
    motion_energy: float
    presence_score: float
    subcarrier_coherence: float
    active_subcarrier_count: int
    signal_quality_score: float
    evidence: list[str]
    extractor_version: str = EXTRACTOR_VERSION

    def numeric_values(self) -> dict[str, float]:
        data = asdict(self)
        return {
            key: float(value)
            for key, value in data.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
