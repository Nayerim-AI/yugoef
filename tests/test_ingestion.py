import asyncio

import pytest

from yugoef.ingestion import CsiIngestionService, DropPolicy, IngestionConfig
from yugoef.protocol import MessageType, PacketHeader, SequenceStatus, serialize_packet


def make_packet(sequence=1, boot_id=10, payload=b"\x01\x02\x03\x04"):
    header = PacketHeader(
        message_type=MessageType.RAW_CSI,
        node_id=1,
        room_id=2,
        boot_id=boot_id,
        sequence=sequence,
        uptime_ms=1000 + sequence,
        wifi_channel=6,
        bandwidth_mhz=20,
        antenna_index=0,
        antenna_count=1,
        subcarrier_count=len(payload) // 2,
        rssi_dbm=-50,
        noise_floor_dbm=-90,
    )
    return serialize_packet(header, payload)


@pytest.mark.asyncio
async def test_ingestion_accepts_valid_packet_and_updates_metrics():
    service = CsiIngestionService(IngestionConfig(queue_maxsize=4))
    result = await service.handle_datagram(make_packet())
    assert result.accepted is True
    assert result.sequence_status == SequenceStatus.FIRST_PACKET
    assert service.metrics.packets_received == 1
    assert service.metrics.valid_packets == 1
    assert service.metrics.queue_depth == 1
    item = await service.queue.get()
    assert item.packet.header.node_id == 1


@pytest.mark.asyncio
async def test_ingestion_rejects_malformed_without_crash():
    service = CsiIngestionService(IngestionConfig(queue_maxsize=4))
    result = await service.handle_datagram(b"bad")
    assert result.accepted is False
    assert service.metrics.packets_received == 1
    assert service.metrics.invalid_packets == 1
    assert service.metrics.queue_depth == 0


@pytest.mark.asyncio
async def test_ingestion_tracks_duplicate_gap_and_out_of_order():
    service = CsiIngestionService(IngestionConfig(queue_maxsize=10))
    assert (await service.handle_datagram(make_packet(1))).sequence_status == SequenceStatus.FIRST_PACKET
    assert (await service.handle_datagram(make_packet(1))).sequence_status == SequenceStatus.DUPLICATE
    assert (await service.handle_datagram(make_packet(4))).sequence_status == SequenceStatus.GAP
    assert (await service.handle_datagram(make_packet(3))).sequence_status == SequenceStatus.OUT_OF_ORDER
    assert service.metrics.duplicate_packets == 1
    assert service.metrics.sequence_gaps == 1
    assert service.metrics.out_of_order_packets == 1


@pytest.mark.asyncio
async def test_ingestion_queue_is_bounded_drop_oldest():
    service = CsiIngestionService(IngestionConfig(queue_maxsize=2, drop_policy=DropPolicy.DROP_OLDEST))
    await service.handle_datagram(make_packet(1))
    await service.handle_datagram(make_packet(2))
    await service.handle_datagram(make_packet(3))
    assert service.metrics.queue_drops == 1
    assert service.metrics.queue_depth == 2
    first = await service.queue.get()
    assert first.packet.header.sequence == 2


@pytest.mark.asyncio
async def test_ingestion_updates_online_node_health():
    service = CsiIngestionService(IngestionConfig(node_timeout_seconds=15))
    await service.handle_datagram(make_packet(1))
    assert service.online_nodes == 1
    assert service.get_node_health("1").online is True
