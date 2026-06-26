# Yugoef — Contactless Room Intelligence Agent

**Qwen Cloud Global Hackathon 2026 — EdgeAgent Track**

An AI agent that turns [RuView](https://github.com/ruvnet/RuView) WiFi sensing signals into natural-language room intelligence. Uses Qwen Cloud API for reasoning, anomaly detection, and trend analysis.

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
| `QWEN_MODEL` | `qwen-plus` | Model to use |
| `RUVIEW_SIMULATED` | `true` | Use simulated sensor data |
| `YUGOEF_HOST` | `0.0.0.0` | Server bind address |
| `YUGOEF_PORT` | `8000` | Server port |

## Hackathon Submission

- **Track:** EdgeAgent
- **Tech Stack:** RuView (Rust/Python) + Qwen Cloud API + FastAPI + Alibaba Cloud ECS
- **Hardware:** ESP32-S3 ($9) + Orange Pi 5 Pro (edge) → Alibaba Cloud ECS (cloud)
- **Cloud Infrastructure:** Alibaba Cloud ap-southeast-1, ECS (Ubuntu), Security Group
- **Architecture:** `docs/architecture-alibaba-cloud.html` (open in browser)
- **Repo:** [https://github.com/Nayerim-AI/yugoef](https://github.com/Nayerim-AI/yugoef)
