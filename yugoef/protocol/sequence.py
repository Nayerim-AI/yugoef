from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .constants import MessageType, UINT32_MAX


class SequenceStatus(str, Enum):
    FIRST_PACKET = "FIRST_PACKET"
    IN_ORDER = "IN_ORDER"
    GAP = "GAP"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    NEW_BOOT = "NEW_BOOT"
    WRAP_AROUND = "WRAP_AROUND"


@dataclass
class SequenceState:
    last_sequence: int
    boot_id: int


class SequenceTracker:
    def __init__(self) -> None:
        self._states: dict[tuple[str, int, MessageType], SequenceState] = {}
        self._latest_boot_by_node_type: dict[tuple[str, MessageType], int] = {}

    def update(self, node_id: str, boot_id: int, message_type: MessageType, sequence: int) -> SequenceStatus:
        message_type = MessageType(message_type)
        node_key = (str(node_id), message_type)
        key = (str(node_id), boot_id, message_type)

        latest_boot = self._latest_boot_by_node_type.get(node_key)
        is_new_boot = latest_boot is not None and boot_id != latest_boot

        if key not in self._states:
            self._states[key] = SequenceState(last_sequence=sequence, boot_id=boot_id)
            self._latest_boot_by_node_type[node_key] = boot_id
            return SequenceStatus.NEW_BOOT if is_new_boot else SequenceStatus.FIRST_PACKET

        state = self._states[key]
        last = state.last_sequence
        if sequence == last:
            return SequenceStatus.DUPLICATE
        if last == UINT32_MAX and sequence == 0:
            state.last_sequence = sequence
            return SequenceStatus.WRAP_AROUND
        expected = (last + 1) & UINT32_MAX
        if sequence == expected:
            state.last_sequence = sequence
            return SequenceStatus.IN_ORDER
        if sequence > last:
            state.last_sequence = sequence
            return SequenceStatus.GAP
        return SequenceStatus.OUT_OF_ORDER
