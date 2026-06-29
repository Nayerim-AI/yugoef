# Yugoef Implementation Plan

**Date:** 2026-06-29  
**Repository:** `Nayerim-AI/yugoef`  
**Prerequisites completed:** `AUDIT.md`, `RUVIEW_REFERENCE_AUDIT.md`, `GAP_ANALYSIS.md`, `TARGET_ARCHITECTURE.md`.

---

## Implementation Rule

All changes happen in the existing Yugoef repository. RuView remains a reference only. No new repository. No Cognitum dependency. No fake production implementation. Mock providers only for tests and explicit demo mode.

---

## Files to Keep

| File/Directory | Reason | Change |
|---|---|---|
| `yugoef/main.py` | Working FastAPI entrypoint. | Refactor gradually; keep existing endpoints compatible. |
| `yugoef/config.py` | Existing env handling. | Expand to AI/CSI/storage config. |
| `yugoef/qwen_client.py` | Existing Qwen OpenAI-compatible client. | Wrap/refactor with provider abstraction and structured JSON validation. |
| `yugoef/event_consumer.py` | Useful compatibility/demo event layer. | Mark simulated path clearly; connect real semantic event flow. |
| `tests/test_basic.py` | Current smoke tests. | Keep and expand. |
| `Dockerfile` | Existing container base. | Update after backend structure stabilizes. |
| `.env.example` | Env documentation. | Add AI_*, CSI_*, STORAGE_* vars. |
| `firmware/esp32-idf/` | Existing RSSI tutorial/demo firmware. | Keep as compatibility/demo; add raw CSI firmware separately. |

---

## Files to Fix

| File | Fix |
|---|---|
| `yugoef/config.py` | Add `AI_ENABLED`, `AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, timeout/retry/cooldown/rate limits; keep QWEN aliases. |
| `yugoef/qwen_client.py` | Add timeout/retry/circuit breaker/rate limiting/JSON schema validation/fallback. |
| `yugoef/main.py` | Add routes for nodes, events, features, ready, metrics; wire real pipeline. |
| `.env.example` | Document safe placeholders and token-plan endpoint. |
| `README.md` | Update actual status after implementation. |
| `scripts/deploy-ecs.sh` | Add new envs, UDP port, storage path, health checks. |

---

## Files to Refactor

| Existing | Target |
|---|---|
| `yugoef/event_consumer.py` | Use as adapter to `anomaly.semantic` or split into compatibility layer. |
| `yugoef/ai_agent.py` | Move structured prompt logic into `yugoef/ai/`; keep wrapper if API imports it. |
| `yugoef/qwen_client.py` | Either keep as compatibility wrapper around `yugoef/ai/qwen.py` or progressively move implementation. |

---

## New Files

### Protocol

```text
yugoef/protocol/__init__.py
yugoef/protocol/constants.py
yugoef/protocol/models.py
yugoef/protocol/parser.py
yugoef/protocol/serializer.py
yugoef/protocol/sequence.py
```

### Ingestion

```text
yugoef/ingestion/__init__.py
yugoef/ingestion/udp_server.py
yugoef/ingestion/http_adapter.py
yugoef/ingestion/service.py
```

### Signal Processing

```text
yugoef/signal_processing/__init__.py
yugoef/signal_processing/iq.py
yugoef/signal_processing/phase.py
yugoef/signal_processing/filters.py
yugoef/signal_processing/windows.py
```

### Feature Extraction

```text
yugoef/feature_extraction/__init__.py
yugoef/feature_extraction/features.py
yugoef/feature_extraction/extractor.py
```

### Anomaly

```text
yugoef/anomaly/__init__.py
yugoef/anomaly/baseline.py
yugoef/anomaly/scoring.py
yugoef/anomaly/state_machine.py
yugoef/anomaly/semantic.py
```

### AI

```text
yugoef/ai/__init__.py
yugoef/ai/provider.py
yugoef/ai/qwen.py
yugoef/ai/schemas.py
```

### Storage

```text
yugoef/storage/__init__.py
yugoef/storage/models.py
yugoef/storage/sqlite.py
yugoef/storage/retention.py
```

### API/Common

```text
yugoef/api/__init__.py
yugoef/api/routes.py
yugoef/api/websocket.py
yugoef/common/__init__.py
yugoef/common/metrics.py
yugoef/common/logging.py
```

### Firmware

```text
firmware/esp32-csi-node/CMakeLists.txt
firmware/esp32-csi-node/main/CMakeLists.txt
firmware/esp32-csi-node/main/main.c
firmware/esp32-csi-node/main/yugoef_protocol.h
firmware/esp32-csi-node/main/yugoef_protocol.c
firmware/esp32-csi-node/main/Kconfig.projbuild
```

### Tests

```text
tests/fixtures/csi_packets.py
tests/test_protocol.py
tests/test_signal_processing.py
tests/test_feature_extraction.py
tests/test_anomaly.py
tests/test_ai_provider.py
tests/test_integration_pipeline.py
```

### Docs

```text
docs/PROTOCOL.md
docs/SIGNAL_PROCESSING.md
docs/ANOMALY_MAPPING.md
docs/IMPLEMENTATION_RESULT.md
docs/FINAL_REPORT.md
```

---

## Files to Remove

None in the first pass. Do not delete existing demo firmware or endpoints until compatibility is verified. If a fake production path remains, label it as demo/simulated rather than deleting immediately.

---

## Dependency Changes

Initial implementation should avoid heavy dependencies.

Likely add:

- `numpy` for signal arrays and phase unwrap if available/acceptable.
- No SciPy initially; implement simple deterministic filters/windowing with Python/numpy to keep install easy.
- No database client beyond stdlib `sqlite3` initially.

Do not add:

- Kafka
- Redis
- Qdrant/Milvus
- TimescaleDB dependency
- Deep learning frameworks
- RuView/RuVector/RuField packages

---

## Database Migration

First pass uses SQLite auto-init schema.

Tables:

1. `nodes`
2. `node_health`
3. `raw_csi_metadata`
4. `feature_vectors`
5. `baselines`
6. `anomaly_events`
7. `ai_interpretations`
8. `room_config`
9. `detector_config`
10. `config_history`

Raw CSI payload storage is optional and disabled by default. Metadata is stored with retention.

---

## API Changes

Backward-compatible:

- Keep `GET /health`.
- Keep `GET /v1/status`.
- Keep `POST /v1/ingest` as JSON compatibility adapter.
- Keep `POST /v1/analyze`, but prefer semantic event input.

Add:

- `GET /ready`
- `GET /v1/nodes`
- `GET /v1/features/latest`
- `GET /v1/events`
- `GET /metrics`
- `WS /v1/ws/telemetry`

Breaking changes: none planned in first pass.

---

## Risks

| Risk | Mitigation |
|---|---|
| ESP32 CSI format differs by chip/IDF config | Add test vectors and parser adapter; document assumptions. |
| UDP packet loss | Sequence/loss metrics and heartbeat. |
| Raw CSI volume too high | Bounded queues and retention. Raw payload disabled by default. |
| False sensing claims | Conservative event names; experimental labels. |
| AI cost/latency | AI rate limit, cooldown, threshold, circuit breaker. |
| Existing API breakage | Keep compatibility endpoints and tests. |
| Alibaba deployment env mistakes | `.env.example`, deploy script validation, no secrets in commands. |

---

## Rollback Plan

1. Use git commits per phase.
2. Existing deployment can roll back to previous commit.
3. Keep old `/v1/ingest` and demo mode during transition.
4. New UDP ingestion disabled unless `CSI_UDP_ENABLED=true`.
5. New AI provider abstraction keeps Qwen env aliases.
6. Storage auto-init writes to configurable file; can disable persistent storage for rollback.

---

## Ordered Implementation

### Phase A — Protocol and docs

1. Write `docs/PROTOCOL.md`.
2. Implement protocol constants/models/parser/serializer.
3. Add protocol tests and fixtures.
4. Commit.

### Phase B — Signal pipeline

1. Implement I/Q amplitude/phase.
2. Implement phase unwrap and simple filtering/windowing.
3. Implement feature extraction.
4. Write `docs/SIGNAL_PROCESSING.md`.
5. Add tests.
6. Commit.

### Phase C — Anomaly engine

1. Implement baseline stats.
2. Implement anomaly scoring.
3. Implement state machine and semantic event mapping.
4. Write `docs/ANOMALY_MAPPING.md`.
5. Add tests.
6. Commit.

### Phase D — Storage and ingestion

1. Implement SQLite schema/store.
2. Implement ingestion service.
3. Implement UDP server disabled by default.
4. Wire HTTP adapter to pipeline.
5. Add integration test fixture: binary CSI → semantic event.
6. Commit.

### Phase E — AI/Qwen

1. Add `AI_*` config.
2. Implement AI provider abstraction.
3. Refactor Qwen client with timeout/retry/circuit breaker/schema validation.
4. Add tests with mock provider.
5. Commit.

### Phase F — API/deployment

1. Add nodes/features/events/metrics/ready routes.
2. Update Docker/deploy scripts and `.env.example`.
3. Add `docs/IMPLEMENTATION_RESULT.md`.
4. Add `docs/FINAL_REPORT.md`.
5. Run full tests.
6. Commit and push.

### Phase G — Firmware raw CSI

1. Add minimal ESP32 CSI firmware under `firmware/esp32-csi-node`.
2. Add serializer matching `docs/PROTOCOL.md`.
3. Add tutorial/flash commands.
4. Compile if ESP-IDF is available; otherwise document unverified hardware build.
5. Commit.

---

## Test Strategy

Run after each major phase:

```bash
python3 -m pytest -q tests/
```

Specific tests:

- protocol valid packet
- invalid magic
- unsupported version
- truncated packet
- invalid payload length
- invalid subcarrier count
- CRC mismatch
- duplicate sequence
- out-of-order sequence
- amplitude/phase known vectors
- phase unwrap
- constant/noisy/motion synthetic windows
- baseline normal/anomaly
- event cooldown/dedup
- AI disabled/mock/invalid JSON/timeout
- integration binary CSI → feature → anomaly → semantic event → mock AI

---

## Completion Criteria

Implementation is acceptable when:

1. Five required pre-coding docs exist.
2. Protocol parser/serializer tests pass.
3. Signal processing tests pass.
4. Anomaly tests pass.
5. Integration fixture test passes without physical ESP32.
6. FastAPI starts and existing endpoints still work.
7. `/v1/status` reports CSI/AI/storage state.
8. Qwen is called only for semantic events and can be disabled.
9. Raw CSI retention is bounded.
10. Final report documents active, heuristic, experimental, and unfinished features.
