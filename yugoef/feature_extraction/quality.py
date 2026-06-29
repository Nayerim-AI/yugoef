from __future__ import annotations


def clamp01(value: float) -> float:
    if value != value:
        return 0.0
    return max(0.0, min(1.0, value))


def linear_quality(value: float, bad: float, good: float) -> float:
    if good == bad:
        return 0.0
    return clamp01((value - bad) / (good - bad))


def inverse_quality(value: float, good: float, bad: float) -> float:
    if bad == good:
        return 0.0
    return clamp01(1.0 - ((value - good) / (bad - good)))


def signal_quality_score(
    *,
    rssi_dbm: int,
    snr_db: int,
    packet_loss_rate: float,
    effective_sample_rate_hz: float,
    subcarrier_coherence: float,
    sample_count: int,
    min_rssi_dbm: int,
    good_rssi_dbm: int,
    min_snr_db: int,
    good_snr_db: int,
    max_packet_loss: float,
    target_sample_rate_hz: float,
) -> float:
    rssi_q = linear_quality(rssi_dbm, min_rssi_dbm, good_rssi_dbm)
    snr_q = linear_quality(snr_db, min_snr_db, good_snr_db)
    loss_q = inverse_quality(packet_loss_rate, 0.0, max_packet_loss)
    rate_q = linear_quality(effective_sample_rate_hz, 0.0, target_sample_rate_hz) if sample_count > 1 else 0.5
    sample_q = clamp01(sample_count / 4.0)
    return clamp01(0.25 * rssi_q + 0.25 * snr_q + 0.20 * loss_q + 0.15 * rate_q + 0.10 * clamp01(subcarrier_coherence) + 0.05 * sample_q)
