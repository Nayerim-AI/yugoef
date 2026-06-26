"""RuView event consumer — subscribes to sensing events.

Supports three modes:
1. MQTT — subscribe to RuView's MQTT topics
2. WebSocket — connect to sensing server WS endpoint
3. Simulated — generate realistic fake events for demo/testing
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from .config import RuViewConfig

log = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], None]


# ── Simulated event generator ────────────────────────────────────────


class SimulatedSensor:
    """Generates realistic fake RuView sensing events for demo."""

    def __init__(self) -> None:
        self._tick = 0
        self._room_state = {
            "occupied": False,
            "motion_level": "none",
            "persons": 0,
            "hr": 0.0,
            "br": 0.0,
        }
        self._last_occupancy_change = 0.0
        self._session_start = time.time()

    def _simulate_tick(self) -> dict[str, Any]:
        """Generate a plausible sensing update."""
        self._tick += 1
        now = time.time()
        elapsed = now - self._session_start

        # Simulate occupancy pattern: empty for first 5s, then occupied
        if elapsed > 5 and not self._room_state["occupied"]:
            self._room_state["occupied"] = True
            self._room_state["persons"] = random.randint(1, 2)
            self._room_state["motion_level"] = "medium"
            self._last_occupancy_change = now

        # Simulate motion decay after entry
        if self._room_state["occupied"]:
            time_since_entry = now - self._last_occupancy_change
            if time_since_entry > 10:
                # Settled — low motion, stable vitals
                self._room_state["motion_level"] = "low"
                self._room_state["hr"] = 68 + random.uniform(-2, 2)
                self._room_state["br"] = 14 + random.uniform(-1, 1)
            elif time_since_entry > 5:
                self._room_state["motion_level"] = "medium"
                self._room_state["hr"] = 72 + random.uniform(-3, 3)
                self._room_state["br"] = 16 + random.uniform(-1, 1)
            else:
                # Just entered — higher motion, elevated vitals
                self._room_state["motion_level"] = "high"
                self._room_state["hr"] = 78 + random.uniform(-5, 5)
                self._room_state["br"] = 18 + random.uniform(-2, 2)

            # Simulate brief movement blips
            if random.random() < 0.05:
                self._room_state["motion_level"] = "high"
                self._room_state[
                    "_blip"
                ] = "brief movement detected - person adjusting position"

        # Simulated event payload matching RuView's SensingUpdate format
        event: dict[str, Any] = {
            "type": "sensing_update",
            "timestamp": now,
            "source": "simulated",
            "tick": self._tick,
            "nodes": [
                {
                    "node_id": 1,
                    "rssi_dbm": -45 + random.uniform(-5, 5),
                    "position": [0.0, 0.0, 0.0],
                }
            ],
            "features": {
                "mean_rssi": -45 + random.uniform(-3, 3),
                "variance": 0.1 + random.uniform(-0.05, 0.05),
                "motion_band_power": (
                    0.8 if self._room_state["motion_level"] == "high"
                    else 0.4 if self._room_state["motion_level"] == "medium"
                    else 0.1
                ) + random.uniform(-0.05, 0.05),
                "breathing_band_power": (
                    0.3 + random.uniform(-0.05, 0.05)
                    if self._room_state["occupied"]
                    else 0.02
                ),
                "dominant_freq_hz": (
                    0.25 + random.uniform(-0.02, 0.02)
                    if self._room_state["occupied"]
                    else 0.0
                ),
                "change_points": random.randint(0, 3),
                "spectral_power": random.uniform(0.1, 0.8),
            },
            "classification": {
                "motion_level": self._room_state["motion_level"],
                "presence": self._room_state["occupied"],
                "confidence": random.uniform(0.85, 0.98),
            },
            "signal_field": {
                "grid_size": [4, 4, 2],
                "values": [random.uniform(0, 1) for _ in range(32)],
            },
            "estimated_persons": (
                self._room_state["persons"]
                if self._room_state["occupied"]
                else 0
            ),
        }

        # Add vitals after person has settled
        if (
            self._room_state["occupied"]
            and time.time() - self._last_occupancy_change > 5
        ):
            event["vital_signs"] = {
                "heart_rate": round(self._room_state["hr"], 1),
                "heart_rate_confidence": random.uniform(0.7, 0.9),
                "breathing_rate": round(self._room_state["br"], 1),
                "breathing_rate_confidence": random.uniform(0.75, 0.95),
            }

        return event

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield simulated events at ~1 Hz."""
        while True:
            yield self._simulate_tick()
            await asyncio.sleep(1.0)


# ── Event consumer ───────────────────────────────────────────────────


@dataclass
class EventConsumer:
    """Consumes RuView events from configured source.

    Also maintains a rolling event buffer for trend analysis.
    """

    config: RuViewConfig
    _buffer: list[dict[str, Any]] = field(default_factory=list)
    _max_buffer: int = 100

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield sensing events from the configured source."""
        if self.config.simulated:
            log.info("Using simulated sensor data")
            sim = SimulatedSensor()
            async for event in sim.events():
                self._buffer.append(event)
                if len(self._buffer) > self._max_buffer:
                    self._buffer.pop(0)
                yield event
        else:
            # Real MQTT or WebSocket mode
            raise NotImplementedError(
                "Real RuView connection not yet implemented. "
                "Set RUVIEW_SIMULATED=true for simulated data."
            )

    @property
    def recent_events(self) -> list[dict[str, Any]]:
        """Return recent event buffer (for trend analysis)."""
        return list(self._buffer)

    def clear_buffer(self) -> None:
        self._buffer.clear()
