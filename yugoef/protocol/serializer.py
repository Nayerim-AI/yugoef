from __future__ import annotations

import struct
import zlib

from .constants import (
    HEADER_LENGTH,
    MAGIC,
    MAX_ANTENNAS,
    MAX_PACKET_SIZE,
    MAX_PAYLOAD_LENGTH,
    MAX_SUBCARRIERS,
    MessageType,
    PROTOCOL_VERSION,
)
from .errors import InvalidPayloadLengthError, InvalidSubcarrierCountError, PacketTooLargeError
from .models import PacketHeader

HEADER_WITHOUT_CRC_FORMAT = ">IBBBBHHIIIBBBBHbbHH"
HEADER_FORMAT = HEADER_WITHOUT_CRC_FORMAT + "I"


def _validate_header_payload(header: PacketHeader, payload: bytes) -> None:
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise PacketTooLargeError(f"payload length {len(payload)} exceeds {MAX_PAYLOAD_LENGTH}")
    if header.message_type == MessageType.RAW_CSI:
        if header.subcarrier_count <= 0 or header.subcarrier_count > MAX_SUBCARRIERS:
            raise InvalidSubcarrierCountError(f"invalid subcarrier count {header.subcarrier_count}")
        if header.antenna_count <= 0 or header.antenna_count > MAX_ANTENNAS:
            raise InvalidSubcarrierCountError(f"invalid antenna count {header.antenna_count}")
        expected = header.subcarrier_count * header.antenna_count * 2
        if len(payload) != expected:
            raise InvalidPayloadLengthError(f"RAW_CSI payload length {len(payload)} != expected {expected}")
    else:
        if header.subcarrier_count != 0:
            raise InvalidSubcarrierCountError("non-RAW_CSI messages must use subcarrier_count=0")


def pack_header_without_crc(header: PacketHeader, payload_length: int) -> bytes:
    return struct.pack(
        HEADER_WITHOUT_CRC_FORMAT,
        MAGIC,
        header.protocol_version,
        int(header.message_type),
        HEADER_LENGTH,
        header.flags,
        header.node_id,
        header.room_id,
        header.boot_id,
        header.sequence,
        header.uptime_ms,
        header.wifi_channel,
        header.bandwidth_mhz,
        header.antenna_index,
        header.antenna_count,
        header.subcarrier_count,
        header.rssi_dbm,
        header.noise_floor_dbm,
        payload_length,
        0,
    )


def serialize_packet(header: PacketHeader, payload: bytes) -> bytes:
    header.message_type = MessageType(header.message_type)
    _validate_header_payload(header, payload)
    payload_length = len(payload)
    header_without_crc = pack_header_without_crc(header, payload_length)
    crc = zlib.crc32(header_without_crc + payload) & 0xFFFFFFFF
    packet = header_without_crc + struct.pack(">I", crc) + payload
    if len(packet) > MAX_PACKET_SIZE:
        raise PacketTooLargeError(f"packet length {len(packet)} exceeds {MAX_PACKET_SIZE}")
    return packet
