from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from yugoef.protocol import (
    CrcMismatchError,
    MessageType,
    ParsedPacket,
    ProtocolError,
    SequenceStatus,
    SequenceTracker,
    parse_packet,
)

from .queue import BoundedIngestionQueue, DropPolicy, IngestionQueueItem


@dataclass
class IngestionConfig:
    max_packet_size: int = 1400
    queue_maxsize: int = 4096
    drop_policy: DropPolicy = DropPolicy.DROP_OLDEST
    node_timeout_seconds: int = 15


@dataclass
class IngestionMetrics:
    packets_received: int = 0
    valid_packets: int = 0
    invalid_packets: int = 0
    crc_mismatch: int = 0
    duplicate_packets: int = 0
    out_of_order_packets: int = 0
    sequence_gaps: int = 0
    queue_drops: int = 0
    queue_depth: int = 0
    online_nodes: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


@dataclass
class NodeHealth:
    node_id: str
    room_id: int
    boot_id: int
    last_seen: float
    last_sequence: int
    last_message_type: MessageType
    rssi_dbm: int
    noise_floor_dbm: int
    online: bool = True


@dataclass(frozen=True)
class IngestionResult:
    accepted: bool
    packet: Optional[ParsedPacket] = None
    sequence_status: Optional[SequenceStatus] = None
    error: Optional[str] = None


class CsiIngestionService:
    def __init__(self, config: IngestionConfig | None = None) -> None:
        self.config = config or IngestionConfig()
        self.metrics = IngestionMetrics()
        self.queue = BoundedIngestionQueue(self.config.queue_maxsize, self.config.drop_policy)
        self.sequence_tracker = SequenceTracker()
        self._node_health: dict[str, NodeHealth] = {}

    @property
    def online_nodes(self) -> int:
        now = time.time()
        for health in self._node_health.values():
            health.online = now - health.last_seen <= self.config.node_timeout_seconds
        self.metrics.online_nodes = sum(1 for h in self._node_health.values() if h.online)
        return self.metrics.online_nodes

    def get_node_health(self, node_id: str) -> NodeHealth:
        return self._node_health[str(node_id)]

    async def handle_datagram(self, data: bytes, received_at: float | None = None) -> IngestionResult:
        received_at = time.time() if received_at is None else received_at
        self.metrics.packets_received += 1
        if len(data) > self.config.max_packet_size:
            self.metrics.invalid_packets += 1
            self._sync_queue_metrics()
            return IngestionResult(False, error="packet_too_large")

        try:
            packet = parse_packet(data)
        except CrcMismatchError as exc:
            self.metrics.invalid_packets += 1
            self.metrics.crc_mismatch += 1
            self._sync_queue_metrics()
            return IngestionResult(False, error=exc.__class__.__name__)
        except ProtocolError as exc:
            self.metrics.invalid_packets += 1
            self._sync_queue_metrics()
            return IngestionResult(False, error=exc.__class__.__name__)

        header = packet.header
        status = self.sequence_tracker.update(
            str(header.node_id), header.boot_id, header.message_type, header.sequence
        )
        if status == SequenceStatus.DUPLICATE:
            self.metrics.duplicate_packets += 1
        elif status == SequenceStatus.OUT_OF_ORDER:
            self.metrics.out_of_order_packets += 1
        elif status == SequenceStatus.GAP:
            self.metrics.sequence_gaps += 1

        self.metrics.valid_packets += 1
        self._node_health[str(header.node_id)] = NodeHealth(
            node_id=str(header.node_id),
            room_id=header.room_id,
            boot_id=header.boot_id,
            last_seen=received_at,
            last_sequence=header.sequence,
            last_message_type=header.message_type,
            rssi_dbm=header.rssi_dbm,
            noise_floor_dbm=header.noise_floor_dbm,
            online=True,
        )
        await self.queue.put(IngestionQueueItem(packet=packet, sequence_status=status, received_at=received_at))
        self.metrics.queue_drops = self.queue.drops
        self._sync_queue_metrics()
        self.online_nodes
        return IngestionResult(True, packet=packet, sequence_status=status)

    def _sync_queue_metrics(self) -> None:
        self.metrics.queue_depth = self.queue.depth
