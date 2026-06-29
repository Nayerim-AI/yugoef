import math

from yugoef.protocol import parse_packet
from yugoef.signal_processing import CsiSignalPipeline, decode_iq, phase_unwrap, top_k_active_subcarriers


def test_known_amplitude_and_phase():
    samples = decode_iq(bytes([3, 4, 0, 255]))  # (3,4), (0,-1)
    assert samples[0].amplitude == 5.0
    assert samples[0].phase == math.atan2(4, 3)
    assert samples[1].amplitude == 1.0
    assert samples[1].phase == -math.pi / 2


def test_phase_unwrap_handles_wrap():
    values = [3.0, 3.1, -3.1, -3.0]
    unwrapped = phase_unwrap(values)
    assert unwrapped[2] > unwrapped[1]
    assert unwrapped[3] > unwrapped[2]


def test_pipeline_builds_bounded_window_and_eviction():
    pipeline = CsiSignalPipeline(window_size=2)
    fixture = parse_packet((__import__("pathlib").Path(__file__).parent / "fixtures" / "csi_normal.bin").read_bytes())
    pipeline.process(fixture)
    pipeline.process(fixture)
    result = pipeline.process(fixture)
    assert result.window_sample_count == 2
    assert result.effective_sample_rate_hz >= 0
    assert len(pipeline.windows) == 1


def test_pipeline_separates_boot_and_channel_state():
    pipeline = CsiSignalPipeline(window_size=4)
    fixture = parse_packet((__import__("pathlib").Path(__file__).parent / "fixtures" / "csi_normal.bin").read_bytes())
    pipeline.process(fixture)
    fixture.header.boot_id += 1
    pipeline.process(fixture)
    assert len(pipeline.windows) == 2


def test_top_k_active_subcarriers_constant_signal():
    rows = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
    assert top_k_active_subcarriers(rows, k=2) == [0, 1]


def test_top_k_active_subcarriers_noisy_signal():
    rows = [[1.0, 2.0, 3.0], [10.0, 2.0, 3.5], [1.0, 2.1, 9.0]]
    assert top_k_active_subcarriers(rows, k=2) == [0, 2]
