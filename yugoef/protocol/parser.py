from __future__ import annotations

import hmac
import struct
import zlib

from .constants import AUTH_FLAG, AUTH_TAG_LENGTH, HEADER_LENGTH, MAGIC, MAX_PACKET_SIZE, MessageType, PROTOCOL_VERSION
from .errors import (
    AuthenticationError,
    CrcMismatchError,
    InvalidMagicError,
    InvalidMessageTypeError,
    InvalidPayloadLengthError,
    PacketTooLargeError,
    TruncatedPacketError,
    UnsupportedVersionError,
)
from .models import PacketHeader, ParsedPacket
from .serializer import HEADER_FORMAT, HEADER_WITHOUT_CRC_FORMAT, _validate_header_payload, auth_tag


def parse_packet(data: bytes, auth_secret: bytes | str | None = None) -> ParsedPacket:
    if isinstance(auth_secret, str):
        auth_secret = auth_secret.encode()
    if len(data) > MAX_PACKET_SIZE:
        raise PacketTooLargeError(f"packet length {len(data)} exceeds {MAX_PACKET_SIZE}")
    if len(data) < HEADER_LENGTH:
        raise TruncatedPacketError(f"packet length {len(data)} shorter than header {HEADER_LENGTH}")

    try:
        (
            magic,
            protocol_version,
            message_type_raw,
            header_length,
            flags,
            node_id,
            room_id,
            boot_id,
            sequence,
            uptime_ms,
            wifi_channel,
            bandwidth_mhz,
            antenna_index,
            antenna_count,
            subcarrier_count,
            rssi_dbm,
            noise_floor_dbm,
            payload_length,
            _reserved,
            crc32,
        ) = struct.unpack(HEADER_FORMAT, data[:HEADER_LENGTH])
    except struct.error as exc:
        raise TruncatedPacketError(str(exc)) from exc

    if magic != MAGIC:
        raise InvalidMagicError(f"invalid magic 0x{magic:08x}")
    if protocol_version != PROTOCOL_VERSION:
        raise UnsupportedVersionError(f"unsupported version {protocol_version}")
    if header_length != HEADER_LENGTH:
        raise InvalidPayloadLengthError(f"invalid header length {header_length}")
    try:
        message_type = MessageType(message_type_raw)
    except ValueError as exc:
        raise InvalidMessageTypeError(f"invalid message type {message_type_raw}") from exc

    total_length = HEADER_LENGTH + payload_length
    if len(data) < total_length:
        raise TruncatedPacketError(f"packet length {len(data)} shorter than expected {total_length}")
    if len(data) != total_length:
        raise InvalidPayloadLengthError(f"packet length {len(data)} does not match expected {total_length}")

    wire_payload = data[HEADER_LENGTH:total_length]
    header_without_crc = data[: struct.calcsize(HEADER_WITHOUT_CRC_FORMAT)]
    computed = zlib.crc32(header_without_crc + wire_payload) & 0xFFFFFFFF
    if computed != crc32:
        raise CrcMismatchError(f"crc mismatch expected 0x{crc32:08x} computed 0x{computed:08x}")

    authenticated = bool(flags & AUTH_FLAG)
    if auth_secret and not authenticated:
        raise AuthenticationError("packet authentication required")
    if authenticated:
        if len(wire_payload) < AUTH_TAG_LENGTH:
            raise AuthenticationError("authenticated packet missing tag")
        payload = wire_payload[:-AUTH_TAG_LENGTH]
        supplied_tag = wire_payload[-AUTH_TAG_LENGTH:]
        if not auth_secret:
            raise AuthenticationError("authenticated packet requires auth_secret")
        expected_tag = auth_tag(auth_secret, header_without_crc, payload)
        if not hmac.compare_digest(supplied_tag, expected_tag):
            raise AuthenticationError("packet authentication failed")
    else:
        payload = wire_payload

    header = PacketHeader(
        protocol_version=protocol_version,
        message_type=message_type,
        header_length=header_length,
        flags=flags,
        node_id=node_id,
        room_id=room_id,
        boot_id=boot_id,
        sequence=sequence,
        uptime_ms=uptime_ms,
        wifi_channel=wifi_channel,
        bandwidth_mhz=bandwidth_mhz,
        antenna_index=antenna_index,
        antenna_count=antenna_count,
        subcarrier_count=subcarrier_count,
        rssi_dbm=rssi_dbm,
        noise_floor_dbm=noise_floor_dbm,
        payload_length=payload_length,
        crc32=crc32,
    )
    _validate_header_payload(header, payload)
    return ParsedPacket(header=header, payload=payload)
