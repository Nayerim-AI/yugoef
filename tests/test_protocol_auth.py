import zlib

import pytest

from yugoef.protocol import AuthenticationError, MessageType, PacketHeader, parse_packet, serialize_packet


def _header():
    return PacketHeader(
        message_type=MessageType.RAW_CSI,
        node_id=1,
        room_id=1,
        boot_id=123,
        sequence=1,
        uptime_ms=1000,
        wifi_channel=6,
        bandwidth_mhz=20,
        antenna_index=0,
        antenna_count=1,
        subcarrier_count=2,
        rssi_dbm=-45,
        noise_floor_dbm=-95,
    )


def test_authenticated_packet_round_trip_strips_auth_trailer():
    payload = bytes([1, 2, 3, 4])
    packet = serialize_packet(_header(), payload, auth_secret=b"secret")

    parsed = parse_packet(packet, auth_secret=b"secret")

    assert parsed.payload == payload
    assert parsed.header.flags & 0x01


def test_authenticated_packet_rejects_wrong_secret():
    packet = serialize_packet(_header(), bytes([1, 2, 3, 4]), auth_secret=b"secret")

    with pytest.raises(AuthenticationError):
        parse_packet(packet, auth_secret=b"wrong")


def test_auth_required_rejects_unsigned_packet():
    packet = serialize_packet(_header(), bytes([1, 2, 3, 4]))

    with pytest.raises(AuthenticationError):
        parse_packet(packet, auth_secret=b"secret")


def test_authenticated_packet_rejects_tamper_even_when_crc_recomputed():
    packet = bytearray(serialize_packet(_header(), bytes([1, 2, 3, 4]), auth_secret=b"secret"))
    packet[-20] ^= 0x01
    crc = zlib.crc32(bytes(packet[:36]) + bytes(packet[40:])) & 0xFFFFFFFF
    packet[36:40] = crc.to_bytes(4, "big")

    with pytest.raises(AuthenticationError):
        parse_packet(bytes(packet), auth_secret=b"secret")
