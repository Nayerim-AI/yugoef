from yugoef.protocol import CrcMismatchError, MessageType, parse_packet


def test_fixture_binaries_are_synthetic_and_parseable():
    for name in ["csi_normal.bin", "csi_motion.bin", "csi_noise.bin"]:
        packet = parse_packet((__import__("pathlib").Path(__file__).parent / "fixtures" / name).read_bytes())
        assert packet.header.message_type == MessageType.RAW_CSI
        assert packet.header.subcarrier_count > 0
        assert packet.payload


def test_invalid_crc_fixture_fails_crc_validation():
    import pytest
    from pathlib import Path
    with pytest.raises(CrcMismatchError):
        parse_packet((Path(__file__).parent / "fixtures" / "csi_invalid_crc.bin").read_bytes())
