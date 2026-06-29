# Yugoef — Contactless Room Intelligence Agent

**Qwen Cloud Global Hackathon 2026 — EdgeAgent Track**

An AI agent that turns [RuView](https://github.com/ruvnet/RuView) WiFi sensing signals into natural-language room intelligence. Uses Qwen Cloud API for reasoning, anomaly detection, and trend analysis.

## Project Concept

Yugoef is a hackathon prototype for **contactless room intelligence**: understanding whether a room is occupied, calm, active, or anomalous without cameras, microphones, or wearable sensors.

Core idea:

1. **WiFi sensing as privacy-preserving perception**
   - An ESP32-class device captures WiFi Channel State Information (CSI).
   - CSI changes when people move, breathe, enter, or leave a room.
   - The system avoids visual/audio surveillance by using radio-signal features only.

2. **Edge-first signal processing**
   - Raw CSI stays on local edge hardware where possible.
   - Orange Pi/Raspberry Pi receives or simulates sensing events.
   - Edge code converts low-level CSI features into structured events: presence, motion level, confidence, dominant frequency, breathing estimate, and optional heart-rate estimate.

3. **Cloud AI reasoning with Qwen**
   - The cloud agent does not need raw CSI.
   - It receives compact structured events and asks Qwen Cloud to explain what is happening in the room.
   - Outputs are human-readable summaries, anomaly alerts, trend analysis, and recommended actions.

4. **Hackathon value proposition**
   - Smart rooms without cameras.
   - Elder-care / safety monitoring without wearables.
   - Building occupancy analytics with better privacy.
   - EdgeAgent pattern: edge sensors produce events, cloud agent reasons and coordinates.

5. **Current hardware fallback**
   - Preferred demo path: ESP32-S3 + RuView.
   - Available fallback: regular ESP32 devkit as a raw/simple CSI capture node, with heavier processing on Orange Pi/Raspberry Pi.
   - If hardware capture is unstable, keep `RUVIEW_SIMULATED=true` and demo the full agent/API flow with realistic simulated events.

6. **Agent memory anchor**
   - If another agent resumes this project, preserve this concept: **Yugoef = privacy-preserving WiFi sensing → structured room events → Qwen-powered room intelligence on Alibaba Cloud ECS**.
   - Do not reframe it as a camera, microphone, chatbot-only, or generic IoT dashboard project.
   - Keep the hackathon story focused on EdgeAgent, contactless sensing, privacy, and Alibaba/Qwen Cloud deployment.

## Architecture

```
┌──────────────────────┐     HTTP/events     ┌─────────────────────────────────────┐
│   EDGE (Homelab)     │    ──────────────▶   │   ALIBABA CLOUD (ap-southeast-1)    │
│                      │                      │                                     │
│  ESP32-S3 ──UDP──▶   │                      │  ┌─────────────────────────────┐    │
│  RuView Rust Server  │                      │  │  ECS Instance                │    │
│  (WiFi CSI sensing)  │                      │  │                              │    │
│  MQTT:1883           │                      │  │  ┌───────────────────────┐   │    │
│  Orange Pi 5 Pro     │                      │  │  │  Yugoef AI Agent      │   │    │
└──────────────────────┘                      │  │  │  FastAPI · :8000      │   │    │
                                              │  │  │                       │   │    │
                                              │  │  │  /v1/analyze          │   │    │
                                              │  │  │  /v1/trend            │   │    │
    ☁ Qwen Cloud API ◀──── HTTP ──────────▶  │  │  │  /v1/detect/anomaly   │   │    │
    (Alibaba Cloud native)                    │  │  └──────────┬────────────┘   │    │
                                              │  │             │                │    │
                                              │  └─────────────┼────────────────┘    │
                                              │                │                     │
                                              │         ┌──────▼──────┐              │
                                              │         │ Event Buffer│              │
                                              │         │ (100 events)│              │
                                              │         └─────────────┘              │
                                              └─────────────────────────────────────┘
```

Full architecture diagram: `docs/architecture-alibaba-cloud.html`

Durable concept note for future agents: `docs/CONCEPT.md`

## Alibaba Cloud Deployment

Yugoef is deployed on **Alibaba Cloud ECS** (ap-southeast-1 Singapore region).

### Prerequisites

1. **Alibaba Cloud account** — [sign up](https://account.qwencloud.com/) (free, $40 hackathon coupon)
2. **ECS instance** — ecs.t6-c1m1.large (free tier eligible, Ubuntu 22.04)
3. **Security group** — open TCP port 8000
4. **Qwen Cloud API key** — from [Qwen Cloud console](https://portal.qwen.ai/)

### Deploy

```bash
# On the ECS instance:
curl -fsSL https://raw.githubusercontent.com/Nayerim-AI/yugoef/main/scripts/deploy-ecs.sh | bash

# Or manually:
git clone https://github.com/Nayerim-AI/yugoef.git /opt/yugoef
cd /opt/yugoef
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set your API key
export QWEN_API_KEY="your-..."
export RUVIEW_SIMULATED=true  # switch to false when connecting RuView

# Run
uvicorn yugoef.main:app --host 0.0.0.0 --port 8000
```

## Quick Start

```bash
# 1. Install dependencies
cd yugoef
pip install -r requirements.txt

# 2. Set your Qwen Cloud API key
export QWEN_API_KEY="your-api-key-here"

# 3. Run the server (simulated mode — no ESP32 needed)
python -m yugoef.main
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/v1/status` | Agent status |
| POST | `/v1/analyze` | Analyze a sensing event |
| POST | `/v1/trend` | Trend analysis from history |
| POST | `/v1/detect/anomaly` | Anomaly detection |
| POST | `/v1/ingest` | Ingest event to buffer |

## Demo Flow

```bash
# Analyze a simulated event
curl -X POST http://localhost:8000/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "type": "sensing_update",
      "classification": {
        "presence": true,
        "motion_level": "medium",
        "confidence": 0.93
      },
      "features": {
        "motion_band_power": 0.45,
        "breathing_band_power": 0.28,
        "dominant_freq_hz": 0.25
      },
      "vital_signs": {
        "heart_rate": 72.5,
        "heart_rate_confidence": 0.85,
        "breathing_rate": 16.2,
        "breathing_rate_confidence": 0.88
      }
    }
  }'
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `QWEN_API_KEY` | — | Qwen Cloud API key (required) |
| `QWEN_BASE_URL` | `https://portal.qwen.ai/v1` | API endpoint |
| `QWEN_MODEL` | `qwen3.7-plus` | Model to use |
| `RUVIEW_SIMULATED` | `true` | Use simulated sensor data |
| `YUGOEF_HOST` | `0.0.0.0` | Server bind address |
| `YUGOEF_PORT` | `8000` | Server port |

## ESP32 Firmware

Tutorial lengkap flash ESP32-IDF untuk WiFi sensing tersedia di:

**→ [docs/ESP32_TUTORIAL.md](docs/ESP32_TUTORIAL.md)**

Firmware project: [`firmware/esp32-idf/`](firmware/esp32-idf/)

Quick start:

```bash
cd firmware/esp32-idf/
idf.py menuconfig          # Set WiFi SSID, password, cloud URL
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

---

## Hackathon Submission

- **Track:** EdgeAgent
- **Tech Stack:** RuView (Rust/Python) + Qwen Cloud API + FastAPI + Alibaba Cloud ECS
- **Hardware:** ESP32-S3 ($9) + Orange Pi 5 Pro (edge) → Alibaba Cloud ECS (cloud)
- **Cloud Infrastructure:** Alibaba Cloud ap-southeast-1, ECS (Ubuntu), Security Group
- **Architecture:** `docs/architecture-alibaba-cloud.html` (open in browser)
- **Repo:** [https://github.com/Nayerim-AI/yugoef](https://github.com/Nayerim-AI/yugoef)
