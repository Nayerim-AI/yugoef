import math
from pathlib import Path

from yugoef.feature_extraction import CsiFeatureExtractor, FeatureConfig
from yugoef.protocol import parse_packet
from yugoef.signal_processing import CsiSignalPipeline

FIXTURES = Path(__file__).parent / "fixtures"


def _packet(name: str):
    return parse_packet((FIXTURES / name).read_bytes())


def _extract_sequence(names, *, window_size=4, config=None):
    pipeline = CsiSignalPipeline(window_size=window_size)
    extractor = CsiFeatureExtractor(config or FeatureConfig())
    vector = None
    for name in names:
        processed = pipeline.process(_packet(name))
        vector = extractor.extract(processed, pipeline)
    assert vector is not None
    return vector


def test_constant_csi_window_produces_low_motion():
    vector = _extract_sequence(["csi_normal.bin"] * 4)
    assert 0.0 <= vector.motion_energy <= 0.15


def test_motion_fixture_has_higher_motion_than_normal_fixture():
    normal = _extract_sequence(["csi_normal.bin"] * 4)
    motion = _extract_sequence(["csi_normal.bin", "csi_motion.bin", "csi_normal.bin", "csi_motion.bin"])
    assert motion.motion_energy > normal.motion_energy


def test_noise_fixture_has_lower_signal_quality_than_normal_fixture():
    normal = _extract_sequence(["csi_normal.bin"] * 4)
    noise = _extract_sequence(["csi_noise.bin"] * 4)
    assert noise.signal_quality_score < normal.signal_quality_score


def test_scores_are_bounded_and_finite():
    vector = _extract_sequence(["csi_normal.bin", "csi_motion.bin", "csi_noise.bin"])
    for value in [vector.motion_energy, vector.presence_score, vector.signal_quality_score]:
        assert math.isfinite(value)
        assert 0.0 <= value <= 1.0
    for value in vector.numeric_values().values():
        assert math.isfinite(value)


def test_snr_is_rssi_minus_noise_floor():
    vector = _extract_sequence(["csi_normal.bin"])
    assert vector.snr_db == vector.rssi_dbm - vector.noise_floor_dbm


def test_packet_loss_reduces_signal_quality_score():
    base = _extract_sequence(["csi_normal.bin"] * 2)
    loss = _extract_sequence(["csi_normal.bin"] * 2, config=FeatureConfig(packet_loss_rate=0.5))
    assert loss.signal_quality_score < base.signal_quality_score


def test_bad_rssi_reduces_signal_quality_score():
    good = _extract_sequence(["csi_normal.bin"], config=FeatureConfig())
    bad = _extract_sequence(["csi_normal.bin"], config=FeatureConfig(rssi_override_dbm=-95))
    assert bad.signal_quality_score < good.signal_quality_score


def test_active_subcarrier_count_matches_processing_result():
    pipeline = CsiSignalPipeline(window_size=4, active_subcarrier_k=5)
    extractor = CsiFeatureExtractor(FeatureConfig())
    processed = pipeline.process(_packet("csi_motion.bin"))
    vector = extractor.extract(processed, pipeline)
    assert vector.active_subcarrier_count == len(processed.active_subcarriers)


def test_node_and_boot_state_do_not_share_windows():
    pipeline = CsiSignalPipeline(window_size=4)
    extractor = CsiFeatureExtractor(FeatureConfig())
    p1 = _packet("csi_normal.bin")
    v1 = extractor.extract(pipeline.process(p1), pipeline)
    p2 = _packet("csi_normal.bin")
    p2.header.boot_id += 1
    v2 = extractor.extract(pipeline.process(p2), pipeline)
    assert v1.window_id != v2.window_id
    assert v2.sample_count == 1


def test_output_is_deterministic_for_same_input():
    first = _extract_sequence(["csi_normal.bin", "csi_motion.bin"])
    second = _extract_sequence(["csi_normal.bin", "csi_motion.bin"])
    assert first == second


def test_evidence_is_condition_based():
    vector = _extract_sequence(["csi_noise.bin"] * 4)
    assert vector.evidence
    assert any("quality" in item or "RSSI" in item or "SNR" in item for item in vector.evidence)
