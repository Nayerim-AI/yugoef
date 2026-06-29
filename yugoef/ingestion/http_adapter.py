from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JsonCompatibilityAdapter:
    """Compatibility buffer for the existing POST /v1/ingest JSON endpoint."""

    max_events: int = 100
    events: list[dict[str, Any]] = field(default_factory=list)

    def ingest(self, event: dict[str, Any]) -> int:
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)
        return len(self.events)
