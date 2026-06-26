"""Tests for Yugoef AI agent."""

import pytest
from yugoef.config import QwenConfig, RuViewConfig, AppConfig
from yugoef.event_consumer import SimulatedSensor


def test_config_defaults():
    cfg = AppConfig.load()
    assert cfg.qwen.base_url == "https://portal.qwen.ai/v1"
    assert cfg.qwen.model == "qwen-plus"
    assert cfg.ruview.simulated is True


def test_simulated_sensor_structure():
    sim = SimulatedSensor()
    import asyncio

    async def get_first():
        async for event in sim.events():
            return event

    event = asyncio.run(get_first())

    assert "type" in event
    assert "timestamp" in event
    assert "classification" in event
    assert "features" in event
    assert event["type"] == "sensing_update"
    assert "motion_level" in event["classification"]
    assert "presence" in event["classification"]


def test_simulated_sensor_transitions():
    """After 5+ seconds, sensor should detect occupancy."""
    sim = SimulatedSensor()
    import asyncio

    async def get_events(n):
        events = []
        async for event in sim.events():
            events.append(event)
            if len(events) >= n:
                return events

    events = asyncio.run(get_events(8))

    # First events: no presence
    assert events[0]["classification"]["presence"] is False

    # After 5 ticks, occupancy should be true
    occupied_events = [e for e in events if e["classification"]["presence"]]
    assert len(occupied_events) >= 1, "Sensor should detect presence after 5s"
