# Yugoef Concept Anchor

Yugoef is a **privacy-preserving contactless room intelligence agent** for the Qwen Cloud Global Hackathon 2026 EdgeAgent track.

## One-line pitch

WiFi sensing detects room presence, motion, and possible vital-sign patterns without cameras or microphones; Qwen Cloud turns those structured sensing events into human-readable room intelligence, anomaly alerts, and trend summaries.

## What this project is

- EdgeAgent hackathon prototype.
- Contactless room intelligence system.
- WiFi CSI sensing pipeline using RuView/ESP32-class hardware.
- Edge processing on Orange Pi/Raspberry Pi.
- Cloud reasoning on Alibaba Cloud ECS via Qwen Cloud API.
- Privacy-focused alternative to camera/microphone monitoring.

## What this project is not

- Not a camera surveillance project.
- Not a microphone/audio monitoring project.
- Not a chatbot-only project.
- Not a generic IoT dashboard.
- Not dependent on uploading raw CSI to the cloud for the demo.

## System story

1. **Sensor layer**
   - ESP32-S3 + RuView is the preferred path.
   - Regular ESP32 devkit can be used as fallback/raw CSI node.
   - If hardware capture fails, simulated events are acceptable for the hackathon demo.

2. **Edge layer**
   - Orange Pi/Raspberry Pi receives raw/simple sensing input.
   - Edge code converts sensing data into compact events:
     - presence
     - motion level
     - confidence
     - dominant frequency
     - breathing estimate
     - optional heart-rate estimate

3. **Cloud agent layer**
   - FastAPI service runs on Alibaba Cloud ECS.
   - Qwen Cloud API performs reasoning over structured events.
   - Endpoints expose analysis, trend detection, anomaly detection, ingestion, status, and health checks.

4. **User value**
   - Smart room awareness without cameras.
   - Elder-care safety monitoring without wearables.
   - Occupancy and motion intelligence for homes, offices, and care rooms.
   - Human-readable AI explanations instead of raw sensor graphs.

## Demo fallback rule

If another agent resumes this repository and no physical CSI setup is ready, keep:

```bash
RUVIEW_SIMULATED=true
```

Then demonstrate the API flow with realistic structured events. Do not block the submission on perfect hardware capture.

## Memory anchor

Preserve this framing:

> **Yugoef = privacy-preserving WiFi sensing → structured room events → Qwen-powered room intelligence on Alibaba Cloud ECS.**

All README, pitch, demo, and Devpost work should align to that sentence.
