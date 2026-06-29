from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from .service import CsiIngestionService

log = logging.getLogger(__name__)


@dataclass
class UdpServerConfig:
    host: str = "0.0.0.0"
    port: int = 5005


class _DatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, service: CsiIngestionService) -> None:
        self.service = service

    def datagram_received(self, data: bytes, addr):  # type: ignore[no-untyped-def]
        asyncio.create_task(self.service.handle_datagram(data))

    def error_received(self, exc):  # type: ignore[no-untyped-def]
        log.warning("UDP CSI receiver error: %s", exc)


class CsiUdpServer:
    def __init__(self, service: CsiIngestionService, config: UdpServerConfig | None = None) -> None:
        self.service = service
        self.config = config or UdpServerConfig()
        self._transport: Optional[asyncio.DatagramTransport] = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: _DatagramProtocol(self.service),
            local_addr=(self.config.host, self.config.port),
        )
        self._transport = transport  # type: ignore[assignment]
        log.info("CSI UDP receiver listening on %s:%s", self.config.host, self.config.port)

    async def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            await asyncio.sleep(0)
