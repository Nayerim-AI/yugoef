from __future__ import annotations

from dataclasses import dataclass

from .constants import MessageType, PROTOCOL_VERSION


@dataclass
class PacketHeader:
    message_type: MessageType
    node_id: int
    room_id: int
    boot_id: int
    sequence: int
    uptime_ms: int
    wifi_channel: int
    bandwidth_mhz: int
    antenna_index: int
    antenna_count: int
    subcarrier_count: int
    rssi_dbm: int
    noise_floor_dbm: int
    flags: int = 0
    protocol_version: int = PROTOCOL_VERSION
    header_length: int = 40
    payload_length: int = 0
    crc32: int = 0


@dataclass(frozen=True)
class ParsedPacket:
    header: PacketHeader
    payload: bytes

    @property
    def key_node_id(self) -> str:
        return str(self.header.node_id)
