from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from yugoef.protocol import ParsedPacket, SequenceStatus


class DropPolicy(str, Enum):
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"


@dataclass(frozen=True)
class IngestionQueueItem:
    packet: ParsedPacket
    sequence_status: SequenceStatus
    received_at: float


class BoundedIngestionQueue:
    def __init__(self, maxsize: int, drop_policy: DropPolicy = DropPolicy.DROP_OLDEST) -> None:
        self._queue: asyncio.Queue[IngestionQueueItem] = asyncio.Queue(maxsize=maxsize)
        self.drop_policy = DropPolicy(drop_policy)
        self.drops = 0

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    async def put(self, item: IngestionQueueItem) -> bool:
        if not self._queue.full():
            self._queue.put_nowait(item)
            return True
        self.drops += 1
        if self.drop_policy == DropPolicy.DROP_NEWEST:
            return False
        try:
            self._queue.get_nowait()
            self._queue.task_done()
        except asyncio.QueueEmpty:
            pass
        self._queue.put_nowait(item)
        return True

    async def get(self) -> IngestionQueueItem:
        item = await self._queue.get()
        self._queue.task_done()
        return item
