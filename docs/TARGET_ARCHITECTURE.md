# Yugoef Target Architecture

**Date:** 2026-06-29  
**Repository:** `Nayerim-AI/yugoef`  
**Architecture Style:** Modular monolith first. No premature microservices.

---

## Architecture Existing

```text
ESP32 DevKit RSSI firmware
  → HTTP JSON POST /v1/ingest
  → FastAPI app yugoef/main.py
  → EventConsumer in simulated mode
  → QwenClient for /v1/analyze
  → in-memory buffer/status/trend/anomaly endpoints
```

Limitations:

- No raw CSI acquisition.
- No binary parser.
- No DSP pipeline.
- No feature extraction from I/Q.
- No persistent storage.
- No WebSocket telemetry.
- No deterministic semantic event engine.
- AI integration exists but not rate-limited/circuit-broken enough for production event flow.

---

## Architecture Target

```text
┌──────────────────────────────┐
│ ESP32 CSI Node               │
│ - WiFi CSI callback          │
│ - Yugoef protocol serializer │
│ - UDP sender                 │
│ - heartbeat/config           │
└──────────────┬───────────────┘
               │ UDP binary / optional HTTP JSON compatibility
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Yugoef Cloud Backend (FastAPI Modular Monolith)              │
│                                                              │
│  ingestion/       UDP + REST ingestion, bounded queues       │
│  protocol/        packet schema, parser, CRC, sequence       │
│  signal/          I/Q → amplitude/phase, filtering, windows  │
│  features/        feature vector extraction                  │
│  anomaly/         baseline, score, state machine, events     │
│  storage/         SQLite/Postgres abstraction + retention    │
│  ai/              Qwen provider, JSON validation, fallback   │
│  api/             REST + WebSocket routes                    │
│  common/          config, logging, metrics, errors           │
└──────────────┬──────────────────────┬────────────────────────┘
               │                      │
               ▼                      ▼
        SQLite/PostgreSQL       Qwen Cloud API
        bounded retention       semantic events only
```

---

## Target Repository Structure

Keep current Python package but expand modularly:

```text
yugoef/
├── yugoef/
│   ├── api/
│   │   ├── routes.py
│   │   └── websocket.py
│   ├── ingestion/
│   │   ├── udp_server.py
│   │   ├── http_adapter.py
│   │   └── service.py
│   ├── protocol/
│   │   ├── constants.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   ├── serializer.py
│   │   └── sequence.py
│   ├── signal_processing/
│   │   ├── iq.py
│   │   ├── filters.py
│   │   ├── phase.py
│   │   └── windows.py
│   ├── feature_extraction/
│   │   ├── features.py
│   │   └── extractor.py
│   ├── anomaly/
│   │   ├── baseline.py
│   │   ├── scoring.py
│   │   ├── state_machine.py
│   │   └── semantic.py
│   ├── ai/
│   │   ├── provider.py
│   │   ├── qwen.py
│   │   └── schemas.py
│   ├── storage/
│   │   ├── models.py
│   │   ├── sqlite.py
│   │   └── retention.py
│   ├── common/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── metrics.py
│   ├── main.py
│   └── qwen_client.py  # compatibility wrapper, later moved under ai/
├── firmware/
│   ├── esp32-idf/      # existing RSSI tutorial/demo firmware
│   └── esp32-csi-node/ # new raw CSI firmware
├── tests/
│   ├── fixtures/
│   ├── test_protocol.py
│   ├── test_signal_processing.py
│   ├── test_anomaly.py
│   └── test_ai.py
├── docs/
├── deployment/
├── docker-compose.yml
└── .env.example
```

---

## Component Responsibilities

### ESP32 CSI Node

Responsibilities:

- Connect to WiFi.
- Enable ESP-IDF CSI capture.
- Serialize raw CSI packets using Yugoef protocol v1.
- Include node_id, room_id hash/index, boot_id, sequence, uptime, channel, bandwidth, RSSI, noise floor, I/Q samples, CRC32.
- Send UDP datagrams to cloud.
- Send heartbeat.
- Receive lightweight config later.

Not allowed:

- No AI API key.
- No Qwen call.
- No LLM inference.
- No medical decision.
- No dependency on Cognitum hardware.

### Cloud Ingestion

Responsibilities:

- UDP listener for raw CSI packets.
- HTTP compatibility adapter for current JSON events.
- Strict packet size bounds.
- CRC validation.
- Per-node sequence tracking.
- Duplicate/out-of-order/loss metrics.
- Bounded queue to DSP pipeline.

### Protocol

Responsibilities:

- Versioned binary schema.
- Parser and serializer parity tests.
- ADR-018 compatibility parser for RuView-like frames.
- Validation errors as typed responses/counters.

### Signal Processing

Pipeline:

```text
Raw I/Q
→ finite validation
→ amplitude = sqrt(I² + Q²)
→ phase = atan2(Q, I)
→ phase unwrap
→ outlier removal
→ filtering/noise reduction
→ normalization
→ sliding window
→ subcarrier selection/coherence
```

### Feature Extraction

Minimal production features:

- rssi_dbm
- noise_floor_dbm
- packet_loss_rate
- amplitude_mean
- amplitude_variance
- phase_variance
- motion_energy
- presence_score
- subcarrier_coherence
- signal_quality_score

Experimental features are present only behind flags and labels:

- breathing_estimate
- heart_rate_estimate
- fall_candidate
- person_count_estimate

### Anomaly Engine

Layered:

1. Data quality anomaly.
2. Feature anomaly.
3. Historical baseline.
4. Temporal state machine.
5. Semantic event mapping.

States:

- UNKNOWN
- ROOM_EMPTY
- OCCUPIED_STILL
- OCCUPIED_ACTIVE
- POSSIBLE_SLEEP
- UNUSUAL_ACTIVITY
- FALL_CANDIDATE
- SIGNAL_DEGRADED
- NODE_OFFLINE

### Qwen AI Integration

Qwen receives semantic events only:

```text
SemanticEvent → AIProvider(Qwen) → structured interpretation JSON → storage/API
```

Qwen does not receive raw CSI arrays and is not the primary anomaly detector.

Controls:

- timeout
- retry with exponential backoff
- circuit breaker
- per-node cooldown
- event deduplication
- max events/minute
- JSON schema validation
- fallback without AI
- token usage logging without secrets

### Storage

Default first implementation: SQLite for simplicity. Future production: PostgreSQL/TimescaleDB if volume requires.

Tables:

- nodes
- node_health
- raw_csi_metadata
- raw_csi_payload optional/bounded
- feature_vectors
- baselines
- anomaly_events
- ai_interpretations
- room_config
- detector_config
- config_history

Raw CSI retention must be bounded.

---

## Sequence: ESP32 to Cloud

```text
ESP32 boot
  → generate boot_id
  → connect WiFi
  → send NODE_HELLO
  → enable CSI callback
  → for each CSI frame:
      capture I/Q + metadata
      assign sequence
      serialize YUGOEF_CSI_V1
      compute CRC32
      UDP send
Cloud UDP server
  → read datagram
  → size check
  → magic/version/type check
  → CRC check
  → parse frame
  → sequence tracker
  → enqueue bounded processing task
  → update node health
```

---

## Sequence: Anomaly to Qwen

```text
FeatureVector
  → baseline update/evaluate
  → anomaly score
  → state machine transition
  → semantic event candidate
  → dedup/cooldown/rate limit
  → store event
  → if AI_ENABLED and score >= threshold:
       call Qwen with structured event
       validate JSON response
       store interpretation
     else:
       produce deterministic fallback
```

---

## Trust Boundaries

```text
Untrusted ESP32/network packet
  boundary: UDP parser validation + CRC + size cap
Trusted backend process
  boundary: storage query validation
External AI provider
  boundary: timeout/retry/circuit breaker/schema validation
Frontend/dashboard
  boundary: no secrets, read-only API unless auth enabled
```

Secrets only in server environment variables.

---

## Protocol Overview

Yugoef protocol v1 will include:

- magic
- protocol_version
- message_type
- header_length
- flags
- node_id
- room_id
- boot_id
- sequence
- uptime_ms
- channel
- bandwidth
- antenna_index/count
- subcarrier_count
- rssi
- noise_floor
- payload_length
- I/Q payload
- crc32

Detailed byte offsets are in `docs/PROTOCOL.md`.

---

## Feature Schema

```json
{
  "node_id": "YUGOEF-001",
  "room_id": "ROOM-001",
  "timestamp": "2026-06-29T00:00:00Z",
  "window_id": "...",
  "sample_count": 64,
  "packet_loss_rate": 0.0,
  "rssi_dbm": -56,
  "noise_floor_dbm": -95,
  "amplitude_mean": 12.3,
  "amplitude_variance": 0.42,
  "phase_variance": 0.31,
  "motion_energy": 0.22,
  "presence_score": 0.71,
  "subcarrier_coherence": 0.80,
  "signal_quality_score": 0.88,
  "experimental": {}
}
```

---

## Event Schema

```json
{
  "event_id": "uuid",
  "node_id": "YUGOEF-001",
  "room_id": "ROOM-001",
  "timestamp": "2026-06-29T00:00:00Z",
  "event_type": "UNUSUAL_MOTION",
  "severity": "medium",
  "confidence": 0.77,
  "anomaly_score": 0.81,
  "evidence": ["motion_energy exceeded EWMA baseline"],
  "feature_snapshot": {},
  "baseline_snapshot": {},
  "detector_version": "yugoef-detector-v1"
}
```

---

## API Contract

Keep existing endpoints where possible:

- `GET /health`
- `GET /ready`
- `GET /v1/status`
- `POST /v1/ingest` compatibility JSON adapter
- `POST /v1/analyze` semantic/Qwen analysis

Add:

- `GET /v1/nodes`
- `GET /v1/nodes/{node_id}`
- `GET /v1/nodes/{node_id}/health`
- `GET /v1/features/latest`
- `GET /v1/events`
- `GET /v1/events/{event_id}`
- `WS /v1/ws/telemetry`
- `GET /metrics` text or JSON counters

UDP binary ingestion is not REST but runs inside the backend process when enabled.

---

## Deployment Topology

### Development

```text
uvicorn yugoef.main:app --reload
SQLite local file
UDP server optional
AI disabled or mock provider
```

### Alibaba ECS

```text
systemd yugoef.service
Python venv
.env server-only secrets
UDP port for CSI
HTTP port 8000
SQLite/Postgres volume
```

### Docker

```text
docker-compose.yml
- yugoef-backend
- optional postgres
- persistent volume
- healthcheck
- restart policy
```

---

## Secret Management

Environment variables:

```text
AI_ENABLED=true
AI_PROVIDER=qwen
AI_BASE_URL=https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
AI_API_KEY=...
AI_MODEL=qwen3.7-plus
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=3
AI_MIN_ANOMALY_SCORE=0.70
AI_COOLDOWN_SECONDS=60
AI_MAX_EVENTS_PER_MINUTE=10
```

Compatibility aliases accepted:

```text
QWEN_BASE_URL
QWEN_API_KEY
QWEN_MODEL
```

Never expose API keys in firmware, dashboard, logs, docs, or commands.

---

## Retry Strategy

- UDP ingestion: no retry; track packet loss and heartbeat.
- Qwen API: exponential backoff with max retries and circuit breaker.
- Storage writes: fail fast with error metric; avoid blocking packet parser indefinitely.
- WebSocket: best-effort broadcast with slow-client drop.

---

## Failure Handling

| Failure | Handling |
|---|---|
| Invalid packet | Reject, increment metric, no crash. |
| CRC mismatch | Reject, metric, evidence in node health. |
| Duplicate sequence | Drop or mark duplicate. |
| Out-of-order | Accept if within tolerance; mark order anomaly. |
| Queue full | Drop newest/oldest by configured policy, metric. |
| AI timeout | Fallback deterministic event. |
| AI invalid JSON | Fallback + validation error metric. |
| Storage unavailable | In-memory bounded fallback, degraded readiness. |
| Node offline | State machine emits NODE_OFFLINE after timeout. |

---

## Health Checks

- `/health`: process alive.
- `/ready`: config loaded, storage available, queue below threshold, optional AI circuit state.
- `/v1/status`: app/model/ingestion/storage/event counters.
- `/metrics`: packet counts, invalid packets, queue depth, events, AI errors.

---

## Logging

Structured logs fields:

- timestamp
- level
- component
- node_id
- room_id
- event_id
- packet_sequence
- error_code

Never log:

- AI API key
- WiFi password
- raw CSI full payload by default
- private IP/domain in public docs

---

## Metrics

Minimum counters/gauges:

- packets_received_total
- packets_valid_total
- packets_invalid_total
- crc_mismatch_total
- duplicate_packets_total
- out_of_order_packets_total
- packet_loss_estimate
- queue_depth
- features_generated_total
- semantic_events_total
- ai_requests_total
- ai_errors_total
- ai_circuit_open
- storage_errors_total

---

## Data Retention

Defaults:

- raw CSI payload: disabled or short retention.
- raw CSI metadata: 7 days.
- feature vectors: 30 days.
- semantic events: 180 days.
- AI interpretations: 180 days.
- metrics aggregate: 30 days.

Retention is enforced by scheduled cleanup or startup cleanup.

---

## Attribution

ESP32 CSI packet and signal-processing design are informed by RuView (MIT License). Yugoef implements an independent subset and does not vendor RuView or require Cognitum.
