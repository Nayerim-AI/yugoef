import pytest

from yugoef.protocol import (
    PROTOCOL_VERSION,
    MessageType,
    PacketHeader,
    SequenceStatus,
    SequenceTracker,
    UnsupportedVersionError,
    InvalidMagicError,
    TruncatedPacketError,
    InvalidPayloadLengthError,
    InvalidSubcarrierCountError,
    CrcMismatchError,
    parse_packet,
    serialize_packet,
)


def sample_raw_packet(sequence=1, boot_id=100, payload=None):
    if payload is None:
        payload = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    header = PacketHeader(
        message_type=MessageType.RAW_CSI,
        node_id=7,
        room_id=3,
        boot_id=boot_id,
        sequence=sequence,
        uptime_ms=123456,
        wifi_channel=6,
        bandwidth_mhz=20,
        antenna_index=0,
        antenna_count=1,
        subcarrier_count=len(payload) // 2,
        rssi_dbm=-55,
        noise_floor_dbm=-95,
        flags=0,
    )
    return header, payload


def test_serializer_parser_round_trip_raw_csi():
    header, payload = sample_raw_packet()
    packet = serialize_packet(header, payload)
    parsed = parse_packet(packet)
    assert parsed.header.protocol_version == PROTOCOL_VERSION
    assert parsed.header.message_type == MessageType.RAW_CSI
    assert parsed.header.node_id == 7
    assert parsed.header.room_id == 3
    assert parsed.header.boot_id == 100
    assert parsed.header.sequence == 1
    assert parsed.header.subcarrier_count == 4
    assert parsed.payload == payload


def test_valid_heartbeat_has_no_iq_payload_requirement():
    header = PacketHeader(
        message_type=MessageType.HEARTBEAT,
        node_id=7,
        room_id=3,
        boot_id=100,
        sequence=2,
        uptime_ms=124000,
        wifi_channel=6,
        bandwidth_mhz=20,
        antenna_index=0,
        antenna_count=1,
        subcarrier_count=0,
        rssi_dbm=-56,
        noise_floor_dbm=-94,
    )
    parsed = parse_packet(serialize_packet(header, b""))
    assert parsed.header.message_type == MessageType.HEARTBEAT
    assert parsed.payload == b""


def test_invalid_magic_is_typed_error():
    header, payload = sample_raw_packet()
    packet = bytearray(serialize_packet(header, payload))
    packet[0:4] = b"BAD!"
    with pytest.raises(InvalidMagicError):
        parse_packet(bytes(packet))


def test_unsupported_version_is_typed_error():
    header, payload = sample_raw_packet()
    packet = bytearray(serialize_packet(header, payload))
    packet[4] = 99
    # fix CRC would still not matter: version is checked before CRC.
    with pytest.raises(UnsupportedVersionError):
        parse_packet(bytes(packet))


def test_truncated_header_is_typed_error():
    with pytest.raises(TruncatedPacketError):
        parse_packet(b"YU")


def test_truncated_payload_is_typed_error():
    header, payload = sample_raw_packet()
    packet = serialize_packet(header, payload)
    with pytest.raises(TruncatedPacketError):
        parse_packet(packet[:-2])


def test_invalid_payload_length_for_raw_csi():
    header, _ = sample_raw_packet(payload=b"\x01\x02\x03")
    with pytest.raises(InvalidPayloadLengthError):
        serialize_packet(header, b"\x01\x02\x03")


def test_invalid_subcarrier_count_for_raw_csi():
    header, payload = sample_raw_packet(payload=b"")
    header.subcarrier_count = 257
    with pytest.raises(InvalidSubcarrierCountError):
        serialize_packet(header, payload)


def test_crc_mismatch_is_typed_error():
    header, payload = sample_raw_packet()
    packet = bytearray(serialize_packet(header, payload))
    packet[-1] ^= 0xFF
    with pytest.raises(CrcMismatchError):
        parse_packet(bytes(packet))


def test_sequence_tracker_duplicate_gap_out_of_order_new_boot_and_wrap():
    tracker = SequenceTracker()
    key = ("7", 100, MessageType.RAW_CSI)
    assert tracker.update(*key, sequence=1) == SequenceStatus.FIRST_PACKET
    assert tracker.update(*key, sequence=2) == SequenceStatus.IN_ORDER
    assert tracker.update(*key, sequence=2) == SequenceStatus.DUPLICATE
    assert tracker.update(*key, sequence=5) == SequenceStatus.GAP
    assert tracker.update(*key, sequence=4) == SequenceStatus.OUT_OF_ORDER
    assert tracker.update("7", 101, MessageType.RAW_CSI, sequence=0) == SequenceStatus.NEW_BOOT

    tracker2 = SequenceTracker()
    assert tracker2.update("7", 200, MessageType.RAW_CSI, sequence=0xFFFFFFFF) == SequenceStatus.FIRST_PACKET
    assert tracker2.update("7", 200, MessageType.RAW_CSI, sequence=0) == SequenceStatus.WRAP_AROUND
