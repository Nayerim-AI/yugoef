"""Qwen Cloud API client — OpenAI-compatible wrapper.

Qwen Cloud exposes an OpenAI-compatible API at its base URL.
This client provides typed methods for chat completions
and structured reasoning specific to Yugoef's use case.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx

from .config import QwenConfig

log = logging.getLogger(__name__)


@dataclass
class QwenResponse:
    """Structured response from Qwen."""

    content: str
    model: str
    usage: dict[str, int]


# Canned responses for demo mode (no API key needed)
_DEMO_ANALYSIS = (
    "Room is occupied with moderate activity. "
    "One person detected with stable vital signs: "
    "heart rate ~72 bpm, breathing rate ~16 bpm. "
    "Motion patterns suggest relaxed activity (e.g., seated at desk). "
    "No anomalies detected."
)

_DEMO_TREND = (
    "Over the last 30 seconds: room occupancy is stable at 1 person. "
    "Activity level has decreased from moderate to low, "
    "suggesting the person has settled into a stationary position. "
    "Vital signs remain steady within normal ranges."
)

_DEMO_ANOMALY = None  # normal conditions


class QwenClient:
    """Client for Qwen Cloud OpenAI-compatible chat API.

    When no API key is configured, falls back to demo/canned
    responses so the server runs without credentials.
    """

    def __init__(self, config: QwenConfig) -> None:
        self.config = config
        self._demo_mode = not config.api_key
        if self._demo_mode:
            self._client = None
        else:
            self._client = httpx.AsyncClient(
                base_url=config.base_url,
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
            )

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> QwenResponse:
        """Send a chat completion request. Returns structured response."""
        if self._demo_mode:
            return QwenResponse(
                content=_DEMO_ANALYSIS,
                model="demo",
                usage={"total_tokens": 0},
            )
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False,
        }

        resp = await self._client.post("/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        return QwenResponse(
            content=choice["message"]["content"],
            model=data["model"],
            usage=data.get("usage", {}),
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        if self._demo_mode:
            yield _DEMO_ANALYSIS
            return
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": full_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True,
        }

        async with self._client.stream(
            "POST", "/chat/completions", json=body
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        yield delta
                except json.JSONDecodeError:
                    continue

    async def analyze_room_event(
        self, event: dict[str, Any]
    ) -> str:
        """Analyze a single RuView sensing event and return NL summary.

        Args:
            event: SensingUpdate from RuView (presence, motion, vitals, etc.)

        Returns:
            Natural-language room intelligence summary.
        """
        system_prompt = (
            "You are Yugoef, a room intelligence agent. "
            "Analyze WiFi sensing data and produce a brief, "
            "human-readable room status. Be concise, factual, "
            "and focus on actionable information. "
            "If vital signs are present, mention trends. "
            "If anomalies are detected, highlight them. "
            "Do NOT speculate beyond what the data supports."
        )

        # Build a compact representation of the event
        features = event.get("features", {})
        classification = event.get("classification", {})
        vitals = event.get("vital_signs")
        persons = event.get("persons", [])
        estimated_persons = event.get("estimated_persons", 0)

        event_summary = {
            "presence": classification.get("presence", False),
            "motion_level": classification.get("motion_level", "none"),
            "confidence": classification.get("confidence", 0.0),
            "persons_detected": len(persons) or estimated_persons,
            "motion_power": features.get("motion_band_power", 0.0),
            "breathing_power": features.get("breathing_band_power", 0.0),
            "dominant_freq_hz": features.get("dominant_freq_hz", 0.0),
            "rssi": features.get("mean_rssi", 0.0),
        }

        if vitals:
            event_summary["vitals"] = {
                "heart_rate_bpm": vitals.get("heart_rate"),
                "heart_rate_confidence": vitals.get("heart_rate_confidence"),
                "breathing_rate_bpm": vitals.get("breathing_rate"),
                "breathing_rate_confidence": vitals.get(
                    "breathing_rate_confidence"
                ),
            }

        messages = [
            {
                "role": "user",
                "content": f"Analyze this room sensing event:\n"
                f"{json.dumps(event_summary, indent=2)}",
            }
        ]

        resp = await self.chat(
            messages, system=system_prompt, temperature=0.3, max_tokens=512
        )
        return resp.content

    async def summarize_trend(
        self, events: list[dict[str, Any]]
    ) -> str:
        """Analyze a window of events and produce a trend summary.

        Args:
            events: List of recent SensingUpdate events.

        Returns:
            Trend analysis in natural language.
        """
        system_prompt = (
            "You are Yugoef, a room intelligence agent. "
            "Given a sequence of WiFi sensing events, "
            "identify trends, patterns, and anomalies. "
            "Focus on: occupancy changes, activity level "
            "trends, vital sign stability, and notable events. "
            "Be concise (2-3 sentences)."
        )

        summary_events = []
        for ev in events:
            cls = ev.get("classification", {})
            feats = ev.get("features", {})
            summary_events.append(
                {
                    "timestamp": ev.get("timestamp", 0),
                    "presence": cls.get("presence"),
                    "motion": cls.get("motion_level"),
                    "confidence": cls.get("confidence"),
                    "motion_power": feats.get("motion_band_power"),
                }
            )

        messages = [
            {
                "role": "user",
                "content": f"Trend analysis for last {len(events)} "
                f"room events:\n{json.dumps(summary_events, indent=2)}",
            }
        ]

        resp = await self.chat(
            messages, system=system_prompt, temperature=0.3, max_tokens=512
        )
        return resp.content

    async def detect_anomaly(
        self, event: dict[str, Any], history: list[dict[str, Any]]
    ) -> Optional[str]:
        """Check if current event is anomalous relative to history.

        Returns:
            Anomaly explanation string, or None if normal.
        """
        system_prompt = (
            "You are an anomaly detection agent for room sensing data. "
            "Compare the current event against typical patterns from history. "
            "Return ONLY an anomaly description if something is unusual. "
            "Return exactly 'NORMAL' if nothing is anomalous. "
            "Examples of anomalies: prolonged inactivity after movement, "
            "unusual occupancy during typical empty hours, "
            "abrupt vital sign changes, unexpected RSSI patterns."
        )

        context = {
            "current_event": {
                "timestamp": event.get("timestamp"),
                "presence": event.get("classification", {}).get("presence"),
                "motion_level": event.get("classification", {}).get(
                    "motion_level"
                ),
                "persons": event.get("estimated_persons"),
            },
            "recent_history_count": len(history),
        }

        messages = [
            {
                "role": "user",
                "content": f"Anomaly check:\n"
                f"{json.dumps(context, indent=2)}",
            }
        ]

        resp = await self.chat(
            messages, system=system_prompt, temperature=0.1, max_tokens=256
        )

        if resp.content.strip().upper() == "NORMAL":
            return None
        return resp.content

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
