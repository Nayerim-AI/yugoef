from __future__ import annotations

import statistics

from yugoef.signal_processing.pipeline import CsiSignalPipeline
from yugoef.signal_processing.models import SignalFrame, SignalPipelineResult

from .models import CsiFeatureVector, FeatureConfig
from .motion import motion_energy
from .presence import presence_score
from .quality import clamp01, signal_quality_score


def _variance(values: list[float]) -> float:
    return statistics.pvariance(values) if len(values) > 1 else 0.0


def _std(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _flatten(rows: list[list[float]]) -> list[float]:
    return [value for row in rows for value in row]


def _phase_derivative_energy(frames: list[SignalFrame], active_subcarriers: list[int]) -> float:
    if len(frames) < 2:
        return 0.0
    active = active_subcarriers or list(range(min(len(frame.phases) for frame in frames)))
    total = 0.0
    count = 0
    for prev, cur in zip(frames, frames[1:]):
        for idx in active:
            if idx < len(prev.phases) and idx < len(cur.phases):
                delta = cur.phases[idx] - prev.phases[idx]
                total += delta * delta
                count += 1
    return total / count if count else 0.0


class CsiFeatureExtractor:
    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config or FeatureConfig()
        self.config.validate()

    def extract(self, processed: SignalPipelineResult, pipeline: CsiSignalPipeline) -> CsiFeatureVector:
        frame = processed.frame
        key = (frame.node_id, frame.boot_id, frame.channel, frame.antenna_index)
        window = pipeline.windows[key]
        frames = list(window.frames)
        amplitude_rows = [item.amplitudes for item in frames]
        phase_rows = [item.phases for item in frames]
        amplitudes = _flatten(amplitude_rows)
        phases = _flatten(phase_rows)

        rssi_dbm = self.config.rssi_override_dbm if self.config.rssi_override_dbm is not None else frame.rssi_dbm
        noise_floor_dbm = frame.noise_floor_dbm
        snr_db = rssi_dbm - noise_floor_dbm
        amp_mean = sum(amplitudes) / len(amplitudes) if amplitudes else 0.0
        amp_var = _variance(amplitudes)
        amp_std = _std(amplitudes)
        phase_var = _variance(phases)
        phase_derivative = _phase_derivative_energy(frames, processed.active_subcarriers)
        motion, amp_motion, phase_motion = motion_energy(
            frames,
            processed.active_subcarriers,
            amplitude_weight=self.config.motion_amplitude_weight,
            phase_weight=self.config.motion_phase_weight,
            energy_scale=self.config.motion_energy_scale,
        )
        active_count = len(processed.active_subcarriers)
        active_ratio = active_count / len(frame.amplitudes) if frame.amplitudes else 0.0
        normalized_phase_var = clamp01(phase_var / 3.14)
        normalized_amp_var = clamp01(amp_var / 100.0)
        presence = presence_score(
            normalized_motion=motion,
            normalized_phase_variance=normalized_phase_var,
            normalized_amplitude_variance=normalized_amp_var,
            active_subcarrier_ratio=active_ratio,
            motion_weight=self.config.presence_motion_weight,
            phase_weight=self.config.presence_phase_weight,
            amplitude_weight=self.config.presence_amplitude_weight,
            active_subcarrier_weight=self.config.presence_active_subcarrier_weight,
        )
        packet_loss_rate = clamp01(self.config.packet_loss_rate)
        quality = signal_quality_score(
            rssi_dbm=rssi_dbm,
            snr_db=snr_db,
            packet_loss_rate=packet_loss_rate,
            effective_sample_rate_hz=processed.effective_sample_rate_hz,
            subcarrier_coherence=processed.subcarrier_coherence,
            sample_count=processed.window_sample_count,
            min_rssi_dbm=self.config.quality_min_rssi_dbm,
            good_rssi_dbm=self.config.quality_good_rssi_dbm,
            min_snr_db=self.config.quality_min_snr_db,
            good_snr_db=self.config.quality_good_snr_db,
            max_packet_loss=self.config.quality_max_packet_loss,
            target_sample_rate_hz=self.config.quality_target_sample_rate_hz,
        )
        evidence: list[str] = []
        if motion > 0.25:
            evidence.append("motion energy elevated from temporal CSI changes")
        if phase_motion > amp_motion and phase_motion > 0.1:
            evidence.append("motion energy elevated from temporal phase changes")
        if phase_var > 0.5:
            evidence.append("phase variance above configured activity scale")
        if packet_loss_rate > 0.0:
            evidence.append("packet loss reduced signal quality")
        if rssi_dbm < self.config.quality_good_rssi_dbm:
            evidence.append("RSSI below preferred operating range")
        if snr_db < self.config.quality_good_snr_db:
            evidence.append("SNR below preferred operating range")
        if active_ratio > 0.10 and motion > 0.1:
            evidence.append("active subcarriers indicate coherent environmental change")
        if quality < 0.5:
            evidence.append("signal quality score is low")

        return CsiFeatureVector(
            node_id=frame.node_id,
            room_id=frame.room_id,
            boot_id=frame.boot_id,
            window_id=f"{frame.node_id}:{frame.boot_id}:{frame.channel}:{frame.antenna_index}",
            window_started_at=frames[0].uptime_ms,
            window_ended_at=frames[-1].uptime_ms,
            sample_count=processed.window_sample_count,
            effective_sample_rate_hz=processed.effective_sample_rate_hz,
            packet_loss_rate=packet_loss_rate,
            rssi_dbm=rssi_dbm,
            noise_floor_dbm=noise_floor_dbm,
            snr_db=snr_db,
            amplitude_mean=amp_mean,
            amplitude_std=amp_std,
            amplitude_variance=amp_var,
            phase_variance=phase_var,
            phase_derivative_energy=phase_derivative,
            motion_energy=motion,
            presence_score=presence,
            subcarrier_coherence=processed.subcarrier_coherence,
            active_subcarrier_count=active_count,
            signal_quality_score=quality,
            evidence=evidence,
            extractor_version=self.config.extractor_version,
        )
