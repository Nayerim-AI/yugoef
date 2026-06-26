"""Yugoef AI Agent — orchestrates RuView events + Qwen Cloud reasoning.

The agent manages the event lifecycle:
1. Receive sensing event from RuView
2. Classify event (normal / anomalous)
3. Send to Qwen Cloud for NL reasoning
4. Track event history for trend analysis
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from .config import AppConfig
from .event_consumer import EventConsumer
from .qwen_client import QwenClient

log = logging.getLogger(__name__)


class YugoefAgent:
    """Main orchestrator for room intelligence."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.qwen = QwenClient(config.qwen)
        self.consumer = EventConsumer(config.ruview)
        self._trend_interval = 30  # seconds between trend summaries
        self._last_trend_time = 0.0
        self._anomaly_cooldown = 15  # seconds between anomaly checks
        self._last_anomaly_time = 0.0
        self._running = False

    async def process_event(
        self, event: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a single sensing event and produce AI insights.

        Returns enriched event with AI analysis fields.
        """
        result: dict[str, Any] = {
            "event": event,
            "ai_analysis": None,
            "trend": None,
            "anomaly": None,
            "processed_at": time.time(),
        }

        now = time.time()
        cls = event.get("classification", {})

        # 1. Always produce NL analysis if presence detected
        if cls.get("presence"):
            analysis = await self.qwen.analyze_room_event(event)
            result["ai_analysis"] = analysis

        # 2. Periodic trend summary
        if now - self._last_trend_time > self._trend_interval:
            if len(self.consumer.recent_events) > 3:
                trend = await self.qwen.summarize_trend(
                    self.consumer.recent_events[-20:]
                )
                result["trend"] = trend
                self._last_trend_time = now

        # 3. Periodic anomaly check
        if now - self._last_anomaly_time > self._anomaly_cooldown:
            if len(self.consumer.recent_events) > 5:
                anomaly = await self.qwen.detect_anomaly(
                    event, self.consumer.recent_events[-10:-1]
                )
                if anomaly:
                    result["anomaly"] = anomaly
                self._last_anomaly_time = now

        return result

    async def run(self) -> None:
        """Main event loop. Consumes events and processes them."""
        self._running = True
        log.info(
            "Yugoef agent started — consuming RuView events "
            "(simulated=%s)",
            self.config.ruview.simulated,
        )

        try:
            async for event in self.consumer.events():
                if not self._running:
                    break
                result = await self.process_event(event)
                if result["ai_analysis"] or result["anomaly"] or result["trend"]:
                    self._emit(result)
        except asyncio.CancelledError:
            pass
        finally:
            await self.qwen.close()
            log.info("Yugoef agent stopped")

    def _emit(self, result: dict[str, Any]) -> None:
        """Emit a processed result. In production this publishes to
        a callback, webhook, or message queue. For now, log it."""
        if result.get("ai_analysis"):
            log.info("🏠 Room insight: %s", result["ai_analysis"][:200])
        if result.get("anomaly"):
            log.warning("⚠️  Anomaly: %s", result["anomaly"][:200])
        if result.get("trend"):
            log.info("📊 Trend: %s", result["trend"][:200])

    def stop(self) -> None:
        self._running = False
