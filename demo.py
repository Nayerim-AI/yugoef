#!/usr/bin/env python3
"""Yugoef demo — end-to-end agent with simulated sensor + Qwen Cloud.

Shows the full flow:
1. Simulated RuView sensor generates events
2. Yugoef agent processes them through Qwen Cloud
3. Prints room insights, trends, and anomaly alerts

Run:
  export QWEN_API_KEY="your_key_here"  # optional, demo mode works without it
  python demo.py
"""

import asyncio
import logging
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

from yugoef.config import AppConfig
from yugoef.ai_agent import YugoefAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


async def main():
    config = AppConfig.load()
    print("=" * 60)
    print("  Yugoef — Contactless Room Intelligence Agent")
    print("  RuView + Qwen Cloud AI")
    print("=" * 60)
    print()
    print(f"  Qwen model: {config.qwen.model}")
    print(f"  API key: {'✓ set' if config.qwen.api_key else '✗ demo mode (no key)'}")
    print(f"  Sensor: {'simulated' if config.ruview.simulated else 'live'}")
    print()

    agent = YugoefAgent(config)

    print("  Agent started. Generating simulated events...")
    print("  Press Ctrl+C to stop")
    print()

    try:
        # Override emit for nice console output
        original_emit = agent._emit

        def demo_emit(result):
            ts = result.get("processed_at", 0)
            event = result.get("event", {})
            cls = event.get("classification", {})
            presence = "👤" if cls.get("presence") else "⬜"
            motion = cls.get("motion_level", "?")
            vitals = event.get("vital_signs", {})
            tick = event.get("tick", 0)

            print(f"\n─── Tick #{tick} {presence} motion={motion} ───")

            if vitals:
                hr = vitals.get("heart_rate", "?")
                br = vitals.get("breathing_rate", "?")
                print(f"   ❤️  HR: {hr} bpm  🌬 BR: {br} bpm")

            if result.get("ai_analysis"):
                print(f"   🏠 {result['ai_analysis']}")

            if result.get("trend"):
                print(f"   📊 {result['trend']}")

            if result.get("anomaly"):
                print(f"   ⚠️  ANOMALY: {result['anomaly']}")

        agent._emit = demo_emit
        await agent.run()

    except KeyboardInterrupt:
        print("\n\n  Stopping agent...")
        agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
