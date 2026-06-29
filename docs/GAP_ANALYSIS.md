# Yugoef Gap Analysis

**Date:** 2026-06-29  
**Main Repository:** https://github.com/Nayerim-AI/yugoef  
**Reference:** https://github.com/ruvnet/RuView  
**Rule:** Yugoef is the only source of truth. RuView is technical reference only.

---

## Summary

Yugoef currently runs as a FastAPI prototype with HTTP JSON event ingestion, simulated RSSI-based events, a Qwen client, and deployment scripts. It does not yet implement the target WiFi CSI cloud pipeline.

RuView provides concrete references for ESP32 CSI capture, binary CSI packet parsing, amplitude/phase conversion, heuristic motion detection, and experimental vitals. Yugoef should implement an independent, smaller, cloud-first pipeline.

---

## Decision Legend

- **Keep existing**: Existing Yugoef component is acceptable.
- **Refactor existing**: Existing component works but needs restructuring.
- **Fix existing**: Existing component is incorrect/incomplete.
- **Adapt from RuView**: Use RuView behavior/design as reference, not wholesale copy.
- **Rewrite based on RuView**: Implement independent Yugoef version based on audited RuView source.
- **Implement new**: No suitable existing implementation.
- **Defer**: Not required for first correct end-to-end version.
- **Remove**: Remove fake/unsafe production implementation.

---

## Capability Gap Table

| Kemampuan | Status Yugoef | Referensi RuView | Keputusan | Prioritas |
|---|---|---|---|---|
| ESP32 CSI capture | Not implemented. Existing firmware sends RSSI JSON, not raw CSI. | `firmware/esp32-csi-node/main/csi_collector.c/h` real ESP-IDF CSI capture. | Rewrite based on RuView | P0 |
| Raw I/Q acquisition | Missing. | ADR-018 raw I/Q int8 pairs after 20-byte header. | Rewrite based on RuView | P0 |
| Node identity | Present as JSON `node_id` in events; no binary protocol identity. | Header byte node_id; NVS config. | Refactor existing + protocol field | P0 |
| Room identity | Partially present in JSON event payload / concept, not enforced. | Not central in ADR-018; higher layers use metadata. | Implement new | P0 |
| Protocol version | Missing in Yugoef packet. | Implicit ADR/magic; no explicit field in ADR-018. | Implement new | P0 |
| Magic number | Missing in Yugoef because JSON-only. | `0xC5110001` raw CSI; sibling magics. | Implement new Yugoef magic + ADR-018 adapter | P0 |
| Message type | Missing. | Sibling packet magics identify packet family. | Implement new enum | P0 |
| Sequence number | Missing in JSON firmware; no duplicate/order tracking. | ADR-018 u32 sequence. | Adapt from RuView | P0 |
| Boot identifier | Missing. | Not in ADR-018 raw CSI. | Implement new | P0 |
| Timestamp | Event timestamp optional/string. No device uptime in binary. | Server timestamp in parser; optional sync packet. | Implement new uptime_ms + server timestamp | P0 |
| WiFi channel | Missing in JSON firmware. | `channel_freq_mhz` in ADR-018. | Adapt from RuView | P0 |
| Bandwidth | Missing. | Derived from flags/subcarrier count; ADR-110 flags. | Adapt with explicit field | P0 |
| Subcarrier count | Missing. | `n_subcarriers` u16, max validation. | Adapt from RuView | P0 |
| RSSI | Present in JSON event. | ADR-018 i8 RSSI. | Keep existing + protocol field | P0 |
| Noise floor | Missing. | ADR-018 i8 noise floor. | Adapt from RuView | P0 |
| Binary payload | Missing. | ADR-018 I/Q bytes. | Rewrite based on RuView | P0 |
| CRC/checksum | Missing. | Raw ADR-018 lacks CRC; feature-state has CRC32. | Implement new CRC32 | P0 |
| UDP transport | Missing. Current firmware uses HTTP POST. | RuView UDP sender real. | Implement new UDP ingestion; keep HTTP adapter | P0 |
| TCP/MQTT transport | Missing. | Some RuView MQTT/client patterns elsewhere, not needed. | Defer | P2 |
| Node heartbeat | Missing as explicit message; status only event count. | Edge/vitals/feature packets; not simple heartbeat. | Implement new | P0 |
| Cloud ingestion | Present for JSON only `/v1/ingest`. | Parser/aggregator patterns. | Refactor existing | P0 |
| Packet validation | Minimal Pydantic event validation only. | `Esp32CsiParser` validates header, sizes, counts. | Rewrite based on RuView | P0 |
| Duplicate detection | Missing. | Sequence available but parser does not enforce duplicates globally. | Implement new | P0 |
| Out-of-order handling | Missing. | Sequence available; sync packet helps timeline. | Implement new | P0 |
| Packet-loss calculation | Missing. | Sequence supports derivation. | Implement new | P0 |
| Amplitude | Missing. | `sqrt(I² + Q²)` in `csi_frame.rs`. | Adapt from RuView | P0 |
| Phase | Missing. | `atan2(Q, I)` in `csi_frame.rs`. | Adapt from RuView | P0 |
| Phase unwrap | Missing. | `phase_sanitizer.rs` and signal crate. | Implement deterministic subset | P1 |
| Filtering | Missing. | Hampel/IIR/windowing modules. | Implement deterministic subset | P1 |
| Windowing | Missing. | Signal crate windows and temporal buffers. | Implement new | P0 |
| Feature extraction | Existing event consumer has simulated feature-like fields only. | `features.rs`, `motion.rs`, vitals modules. | Rewrite based on RuView | P0 |
| Motion energy | Simulated/mock in event consumer. | `motion.rs` variance/correlation/phase/Doppler heuristic. | Implement deterministic heuristic | P0 |
| Presence score | Simulated/mock. | `MotionDetector` heuristic `human_detected`/confidence. | Implement conservative heuristic | P0 |
| Breathing estimate | Not implemented. | `breathing.rs` heuristic IIR + zero crossing. | Defer / experimental | P2 |
| Heart-rate estimate | Not implemented. | `heartrate.rs` heuristic IIR + autocorrelation. | Defer / experimental | P2 |
| Fall candidate | Not implemented except possible demo anomaly label. | Firmware edge tests/heuristics. | Defer / experimental | P2 |
| Signal quality | Missing. | Confidence components and RSSI/noise available. | Implement new | P0 |
| Historical baseline | Missing. Current buffer is transient events. | Welford/z-score patterns in vitals anomaly; calibration modules. | Implement new with Welford/EWMA/MAD | P0 |
| Novelty score | Missing. | Advanced calibration/novelty patterns exist but mixed. | Implement simple deterministic baseline distance | P1 |
| Anomaly score | Simulated in `/v1/detect/anomaly`. | Welford/z-score and heuristic detectors. | Refactor existing | P0 |
| Temporal state machine | Missing. | Some motion history/adaptive threshold; not Yugoef states. | Implement new | P1 |
| Semantic events | Partially in JSON/demo; not deterministic from features. | Event concepts in RuView/RuField not directly adopted. | Implement new | P0 |
| Raw CSI storage | Missing. | RuView has data examples; no Yugoef storage. | Implement bounded metadata + optional raw retention | P1 |
| Feature storage | Missing. | RuView stores/uses features in Rust pipeline; not Yugoef. | Implement new | P1 |
| Event storage | Missing; memory only. | Archive has DB patterns. | Implement new SQLite first | P1 |
| REST API | Basic FastAPI endpoints exist. | Archive v1 API patterns. | Keep existing + extend | P0 |
| WebSocket | Missing. | RuView archive/v2 has WebSocket telemetry patterns. | Implement new | P1 |
| Qwen integration | Present `QwenClient`, but still model/base env naming inconsistent with target AI_* abstraction. | Not the focus in RuView. | Refactor existing | P0 |
| Dashboard | Missing in Yugoef codebase. README mentions future. | RuView has dashboard/ui but not to copy. | Implement new minimal | P2 |
| Alert | Missing except demo response. | RuView alert concepts in anomaly modules. | Implement semantic event API first | P1 |
| Unit testing | Minimal `tests/test_basic.py`. | RuView has broad parser/DSP tests. | Add tests | P0 |
| Integration testing | Missing full CSI pipeline fixture. | RuView parser tests and mock CSI. | Implement new fixtures | P0 |
| Docker deployment | Dockerfile exists minimal. No compose/db/retention. | RuView has Docker/deploy references. | Fix existing | P1 |
| Logging | Basic Uvicorn/app logging only. | RuView has structured patterns; not required. | Improve existing | P1 |
| Metrics | Missing. | RuView monitoring references. | Implement minimal counters endpoint | P1 |
| Authentication | Missing. | Archive v1 auth/rate-limit middleware. | Defer for local/private; P1 for public | P1 |

---

## P0 Fix Set

P0 is required for a real end-to-end CSI pipeline.

1. Protocol document and parser.
2. ESP32 firmware raw CSI capture + UDP send.
3. Cloud UDP binary ingestion.
4. Packet validation and sequence tracking.
5. I/Q to amplitude/phase conversion.
6. Per-node sliding windows.
7. Minimal feature extraction.
8. Baseline and deterministic anomaly score.
9. Semantic event creation.
10. Qwen call only on semantic events, never raw CSI.
11. Unit/integration tests with binary fixtures.

---

## P1 Fix Set

1. Phase unwrap and filtering.
2. Historical storage with retention.
3. WebSocket telemetry.
4. Metrics endpoint.
5. Docker Compose and production profile.
6. Auth/rate limiting if exposed publicly.
7. Temporal state machine with hysteresis/cooldown.
8. Structured logging.

---

## P2 / Deferred

1. Breathing estimate.
2. Heart-rate estimate.
3. Fall candidate.
4. Person-count estimate.
5. BVP/Doppler velocity profile.
6. Dashboard polish.
7. MQTT/TCP transports.
8. Advanced cross-room and through-wall claims.

All P2 sensing features must be marked:

- EXPERIMENTAL
- HEURISTIC
- NOT MEDICAL GRADE where relevant
- REQUIRES CALIBRATION

---

## Current Yugoef Components to Keep

| Component | Why Keep | Required Change |
|---|---|---|
| FastAPI app `yugoef/main.py` | Working API skeleton and deployment target. | Refactor routers/services; add CSI routes. |
| Config `yugoef/config.py` | Central env parsing exists. | Add AI_* and CSI/storage envs; keep Qwen compatibility aliases. |
| Qwen client `yugoef/qwen_client.py` | Already handles OpenAI-compatible Qwen and demo fallback. | Add provider abstraction, circuit breaker, JSON schema validation, rate limits. |
| Event consumer `yugoef/event_consumer.py` | Useful demo/event buffer concept. | Replace simulated production path with real feature/event pipeline. |
| Dockerfile | Minimal container path. | Add compose, health/readiness, storage volume. |
| Tests | Smoke tests exist. | Expand heavily. |

---

## Existing Yugoef Components to Avoid Treating as Production

| Component | Issue | Action |
|---|---|---|
| `firmware/esp32-idf` RSSI firmware | Not raw CSI; only RSSI event simulator. | Replace/extend with `firmware/esp32-csi-node`. |
| Event trend/anomaly endpoints | Simulated data, no CSI feature basis. | Refactor to use real feature store. |
| In-memory event buffer | Loses data on restart, unbounded risk if extended. | Bound + persistent storage. |
| Qwen demo mode | Useful without key but not real AI result. | Keep explicit `AI_ENABLED=false/demo` labeling. |
| README architecture claims | Ahead of implementation. | Update docs with actual status. |

---

## Implementation Direction

Yugoef should move from:

```text
ESP32 RSSI JSON → FastAPI event buffer → Qwen demo/analyze
```

to:

```text
ESP32 raw CSI binary UDP
→ packet parser/validator
→ sequence/loss tracker
→ I/Q amplitude/phase
→ sliding window DSP
→ feature extraction
→ baseline/anomaly engine
→ semantic events
→ Qwen explanation on selected events
→ REST/WebSocket/dashboard/storage
```

Keep HTTP JSON `/v1/ingest` as compatibility/demo adapter, but real CSI must use binary protocol ingestion.

---

## Attribution Decision

Because protocol and DSP design are informed by RuView, Yugoef docs should include attribution in `docs/PROTOCOL.md`, `docs/SIGNAL_PROCESSING.md`, and `docs/FINAL_REPORT.md`:

> ESP32 CSI packet and signal-processing design were informed by RuView (MIT License). Yugoef implements an independent subset and does not vendor RuView or require Cognitum.

---

## Next Required Document

Proceed to `docs/TARGET_ARCHITECTURE.md`, then `docs/IMPLEMENTATION_PLAN.md` before coding.
