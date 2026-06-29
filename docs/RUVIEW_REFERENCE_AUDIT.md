# RuView Reference Source Audit

**Audit Date:** 2026-06-29  
**Reference Repository:** https://github.com/ruvnet/RuView  
**Reference Commit:** `1a049299`  
**Yugoef usage:** Technical reference only. Not copied wholesale. Cognitum and RuView-specific hardware/software are not required dependencies.

---

## Scope

Audit ini membaca source code RuView yang relevan untuk Yugoef:

- ESP32 WiFi CSI capture firmware.
- Binary CSI packet format.
- CSI parser/validation.
- Signal processing primitives.
- Feature extraction.
- Motion/presence heuristics.
- Breathing/heart-rate experimental extractors.
- Baseline/anomaly patterns.
- REST/WebSocket/telemetry references where useful.

RuView adalah codebase besar dengan banyak modul experimental, archive, swarm, WASM, mmWave, 802.11bf, RuField, Cognitum, and simulation modules. Yugoef hanya mengambil pola teknis yang sesuai dengan arsitektur cloud modular monolith.

---

## High-Level Findings

1. **RuView memiliki implementasi nyata untuk raw ESP32 CSI capture dan UDP streaming** di `firmware/esp32-csi-node`.
2. **Format raw CSI utama adalah ADR-018 binary frame** dengan magic `0xC5110001`, header 20 byte, little-endian, lalu I/Q int8 pairs.
3. **Parser cloud Rust tersedia dan robust** di `v2/crates/wifi-densepose-hardware/src/esp32_parser.rs`.
4. **Amplitude/phase calculation sederhana dan jelas** di `csi_frame.rs`.
5. **Signal processing Rust cukup lengkap**, tetapi banyak modul bersifat advanced/experimental; Yugoef sebaiknya adapt subset deterministic terlebih dahulu.
6. **Presence/motion detection berbasis heuristic weights**, bukan model terlatih production.
7. **Breathing dan heart-rate ada implementasi heuristic**, tetapi harus diberi label EXPERIMENTAL / NOT MEDICAL GRADE / REQUIRES CALIBRATION.
8. **Fall candidate dan person count tidak boleh diklaim akurat**; di firmware/test ditemukan heuristic presence/fall, bukan evidence validasi klinis/production.
9. **Banyak modul RuView mengandung mock/stub/placeholder**, terutama QEMU mock CSI, no-op stubs untuk target non-C6, NDP placeholder, calibration proof placeholder, dan advanced features.
10. **Lisensi RuView MIT**, tetapi adaptasi tetap perlu attribution jika mengambil desain/format/algoritma secara eksplisit.

---

## Repository Structure Relevant to Yugoef

| Area | Path | Relevance |
|---|---|---|
| ESP32 CSI firmware | `firmware/esp32-csi-node/` | Referensi utama firmware CSI, UDP sender, NVS config, mock generator, tests. |
| Firmware CSI collector | `firmware/esp32-csi-node/main/csi_collector.c/h` | Source capture CSI via ESP-IDF callback and binary serializer. |
| Firmware sender | `firmware/esp32-csi-node/main/stream_sender.c/h` | UDP transport pattern. |
| Firmware config | `firmware/esp32-csi-node/main/nvs_config.c/h`, `Kconfig.projbuild` | Runtime node config, WiFi, target host. |
| Firmware edge processing | `firmware/esp32-csi-node/main/edge_processing.c/h` | On-device feature/vitals; not recommended as mandatory for Yugoef cloud-first design. |
| Feature-state packet | `firmware/esp32-csi-node/main/rv_feature_state.c/h` | CRC32 packet pattern; useful for Yugoef protocol. |
| Rust hardware parser | `v2/crates/wifi-densepose-hardware/src/esp32_parser.rs` | Parser for ADR-018 raw CSI frame. |
| Rust CSI frame types | `v2/crates/wifi-densepose-hardware/src/csi_frame.rs` | Hardware-agnostic frame model and amplitude/phase conversion. |
| Sync packet | `v2/crates/wifi-densepose-hardware/src/sync_packet.rs` | Optional timestamp alignment idea. |
| Signal processing | `v2/crates/wifi-densepose-signal/src/` | DSP and feature extraction reference. |
| Vitals | `v2/crates/wifi-densepose-vitals/src/` | Breathing/HR heuristic extractors; experimental only. |
| Archive Python v1 | `archive/v1/src/` | FastAPI/WebSocket/database patterns, older code. Use cautiously. |

---

## Module Audit

### 1. ESP32 CSI Capture

| Field | Detail |
|---|---|
| Path | `firmware/esp32-csi-node/main/csi_collector.c`, `csi_collector.h` |
| Purpose | Enable ESP-IDF WiFi CSI collection and serialize raw CSI frames. |
| Key symbols | `CSI_MAGIC`, `CSI_HEADER_SIZE`, `CSI_MAX_FRAME_SIZE`, `s_sequence`, CSI callback/serialization functions. |
| Input | ESP-IDF CSI callback data (`wifi_csi_info_t` style data), node id, WiFi metadata. |
| Output | Binary ADR-018 CSI packet sent via stream sender. |
| Algorithm | Copy ESP CSI `info->buf` I/Q bytes after a fixed header; sequence increments monotonically. |
| Packet | Magic `0xC5110001`, node_id, antenna count, subcarrier count, frequency MHz, sequence, RSSI, noise floor, PPDU byte, flags, I/Q pairs. |
| Thresholds | Max subcarriers 256, max antennas 4 from parser; firmware max frame `20 + 4*256*2`. |
| Real/placeholder | CSI capture and serializer are real. NDP injection has TODO placeholder. Mock CSI exists for QEMU tests. |
| Suitable for Yugoef | Yes, but rewrite minimal firmware around ESP-IDF CSI and Yugoef protocol; do not copy full RuView firmware. |
| Risk | ESP-IDF CSI byte format differs by target/firmware config; raw I/Q assumptions need test vectors from real board. |

Relevant observed protocol comments:

```text
[0..3]   Magic: 0xC5110001 LE
[4]      node_id
[5]      n_antennas
[6..7]   n_subcarriers LE u16
[8..11]  channel frequency MHz LE u32
[12..15] sequence LE u32
[16]     RSSI i8
[17]     noise floor i8
[18]     PPDU type
[19]     flags
[20..]   I/Q pairs as signed bytes, I then Q
```

### 2. UDP Transport

| Field | Detail |
|---|---|
| Path | `firmware/esp32-csi-node/main/stream_sender.c/h`, `main.c` |
| Purpose | Send CSI packets to configured aggregator/server over UDP. |
| Input | Serialized CSI frames and feature/vitals packets. |
| Output | UDP datagrams. |
| Dependency | lwIP sockets, ESP-IDF networking. |
| Real/placeholder | Real transport; mocked in QEMU. |
| Suitable for Yugoef | Yes conceptually. Yugoef can support UDP raw CSI ingestion plus existing HTTP JSON adapter. |
| Risk | UDP loss/out-of-order expected. Cloud must implement duplicate/out-of-order/loss tracking. |

### 3. ADR-018 Parser

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-hardware/src/esp32_parser.rs` |
| Class | `Esp32CsiParser` |
| Constants | `ESP32_CSI_MAGIC = 0xC5110001`, sibling packet magics `0xC5110002..0xC5110007`, `HEADER_SIZE = 20`, `MAX_SUBCARRIERS = 256`, `MAX_ANTENNAS = 4` |
| Functions | `parse_frame(data)`, `parse_stream(data)`, `ruview_sibling_packet_name(magic)` |
| Input | Binary byte buffer from UDP/stream. |
| Output | `CsiFrame` + consumed byte count, or explicit `ParseError`. |
| Validation | Header size, magic, antenna count, subcarrier count, total frame size, sibling packet classification. |
| Algorithm | Little-endian decode fixed header; parse I/Q byte pairs; derive subcarrier index and bandwidth. |
| Real/placeholder | Real parser with unit tests. |
| Suitable for Yugoef | Strong reference. Python equivalent should be implemented with same validation plus CRC/version extension if Yugoef protocol evolves. |
| Risk | ADR-018 lacks boot_id, protocol_version field separate from magic, room_id, checksum/CRC for raw CSI. Yugoef should version protocol explicitly. |

### 4. CSI Frame Model and Amplitude/Phase

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-hardware/src/csi_frame.rs` |
| Structs | `CsiFrame`, `CsiMetadata`, `SubcarrierData`, `Bandwidth`, `PpduType`, `Adr018Flags` |
| Methods | `to_amplitude_phase()`, `mean_amplitude()`, `is_valid()` |
| Formula | amplitude = `sqrt(I² + Q²)`, phase = `atan2(Q, I)` |
| Input | Parsed I/Q per subcarrier. |
| Output | amplitude vector, phase vector. |
| Real/placeholder | Real and simple. |
| Suitable for Yugoef | Yes. Implement in Python exactly and test with vectors. |
| Risk | Phase needs unwrap/sanitization across time; single-frame `atan2` is only first step. |

### 5. Sync Packet / Timestamp Alignment

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-hardware/src/sync_packet.rs`, firmware `csi_collector.c` sync section |
| Purpose | Pair sequence number to mesh-aligned timestamps. |
| Magic | `0xC511A110` |
| Input | Local time, epoch/mesh time, high-water CSI sequence. |
| Output | 28-byte sync packet and interpolation method. |
| Real/placeholder | Implemented with tests; C6-only time-sync paths contain no-op stubs on other targets. |
| Suitable for Yugoef | Optional future feature. For first implementation, use device uptime and server received timestamp. |
| Risk | Timestamps can be misleading without clock sync; document source of time. |

### 6. CSI Processor / Preprocessing

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-signal/src/csi_processor.rs`, `phase_sanitizer.rs`, `hampel.rs`, `features.rs` |
| Purpose | Preprocessing, phase sanitization, feature extraction. |
| Input | CSI amplitude/phase windows. |
| Output | cleaned windows and feature structs. |
| Algorithms | Noise removal, windowing, normalization, phase unwrapping/sanitization, Hampel-style outlier removal, feature statistics. |
| Real/placeholder | Core modules appear real and tested, but not all advanced claims should be adopted. |
| Suitable for Yugoef | Adapt deterministic subset: finite checks, outlier removal, phase unwrap, window statistics. |
| Risk | Rust API does not directly drop into Python; parameters need calibration. |

### 7. Body Velocity Profile

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-signal/src/bvp.rs` |
| Function | `extract_bvp(csi_temporal, sample_rate, config)` |
| Purpose | Velocity × time representation from CSI temporal amplitude. |
| Input | `num_samples × num_subcarriers` amplitude matrix. |
| Output | `BodyVelocityProfile` matrix, velocity bins, time/velocity resolution. |
| Algorithm | Hann window STFT per subcarrier, remove DC, aggregate magnitude, map Doppler frequency to velocity `v = f_doppler * λ / 2`. |
| Defaults | window 128, hop 32, carrier 5GHz, velocity bins 64, max velocity 2m/s. |
| Real/placeholder | Real deterministic implementation with synthetic tests. |
| Suitable for Yugoef | P2. Useful after raw CSI pipeline stable. Not needed for first minimal feature set. |
| Risk | Requires reliable sample rate and temporal windows; cross-room accuracy not guaranteed. |

### 8. Motion / Presence Detection

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-signal/src/motion.rs` |
| Classes | `MotionDetector`, `MotionScore`, `MotionAnalysis`, `HumanDetectionResult` |
| Purpose | Heuristic human presence/motion score from CSI features. |
| Input | `CsiFeatures` with amplitude, phase, correlation, optional Doppler. |
| Output | motion score, confidence, human_detected flag. |
| Algorithms | Weighted fusion of variance, correlation, phase, optional Doppler; temporal smoothing; optional adaptive threshold. |
| Thresholds | human detection threshold default 0.8, motion threshold 0.3, smoothing 0.9, history 100. Empirical constants documented as heuristic. |
| Real/placeholder | Implemented heuristic, not validated production model. |
| Suitable for Yugoef | Yes as deterministic heuristic baseline, but mark as heuristic and calibrate per room. |
| Risk | Human detection claim must be conservative; use `presence_score`, not definitive identity/person count. |

### 9. Breathing Extraction

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-vitals/src/breathing.rs` |
| Class | `BreathingExtractor` |
| Purpose | Respiratory-rate estimate from CSI amplitude residuals. |
| Input | residuals per subcarrier + weights. |
| Output | `VitalEstimate` BPM/confidence/status or None. |
| Algorithm | Weighted residual fusion, 2nd-order IIR bandpass 0.1–0.5 Hz, zero-crossing frequency estimate, SNR-like confidence. |
| Defaults | 56 subcarriers, 100 Hz, 30 s window. |
| Real/placeholder | Implemented heuristic with synthetic tests. |
| Suitable for Yugoef | Experimental only. Add after baseline CSI quality proves adequate. |
| Risk | Not medical grade; zero-crossing is fragile; requires stable sample rate, posture, calibration, ground truth. |

### 10. Heart Rate Extraction

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-vitals/src/heartrate.rs` |
| Class | `HeartRateExtractor` |
| Purpose | Heart-rate estimate from phase-coherence weighted signal. |
| Input | residuals + unwrapped phases. |
| Output | `VitalEstimate` BPM/confidence/status or None. |
| Algorithm | Phase-coherence weighted fusion, IIR bandpass 0.8–2.0 Hz, autocorrelation peak detection. |
| Thresholds | plausible HR band 40–180 BPM; min 4 subcarriers; 5 s minimum history. |
| Real/placeholder | Implemented heuristic with synthetic tests and noise guard. |
| Suitable for Yugoef | Defer / experimental. Do not expose as production health/medical result. |
| Risk | Very weak signal, high false positives, needs controlled setup and labeled evaluation. |

### 11. Vital Anomaly Detector

| Field | Detail |
|---|---|
| Path | `v2/crates/wifi-densepose-vitals/src/anomaly.rs` |
| Class | `VitalAnomalyDetector` |
| Purpose | Detect RR/HR anomalies using running stats and clinical thresholds. |
| Input | `VitalReading`. |
| Output | `AnomalyAlert[]`. |
| Algorithm | Welford running mean/std, z-score, fixed thresholds for apnea/tachycardia/etc. |
| Defaults | window 60, z threshold 2.5. |
| Real/placeholder | Implemented deterministic logic; depends on experimental vital estimates. |
| Suitable for Yugoef | The Welford/z-score pattern is useful for baseline anomaly, but not clinical labels. |
| Risk | Clinical alert naming unsafe for Yugoef unless validated; use room-signal anomaly names instead. |

### 12. Feature-State Packet with CRC32

| Field | Detail |
|---|---|
| Path | `firmware/esp32-csi-node/main/rv_feature_state.c/h` |
| Purpose | Compact feature-state packet with magic, seq, timestamp, CRC32. |
| Input | Edge-derived features. |
| Output | Fixed packet with IEEE CRC32 over bytes except trailing crc32. |
| Real/placeholder | Implemented with host tests. |
| Suitable for Yugoef | CRC32 pattern suitable for Yugoef protocol. Raw CSI packet should include checksum/CRC. |
| Risk | Feature-state is RuView-specific; Yugoef should define its own schema. |

### 13. Archive FastAPI / WebSocket / Database

| Field | Detail |
|---|---|
| Path | `archive/v1/src/api`, `archive/v1/src/database`, `archive/v1/src/sensing` |
| Purpose | Older Python service patterns: API routers, auth/rate-limit middleware, WebSocket stream, database migrations. |
| Real/placeholder | Mixed archived code, likely stale. |
| Suitable for Yugoef | Use only for pattern comparison. Do not depend or copy directly. |
| Risk | Archive may not reflect current RuView v2 architecture; may include obsolete assumptions. |

---

## Implemented vs Placeholder Classification

### Implemented and Useful

- ESP32 CSI callback + binary frame serialization (`csi_collector.c`).
- UDP stream sender concept (`stream_sender.c`).
- ADR-018 parser (`esp32_parser.rs`).
- CSI frame model, amplitude/phase conversion (`csi_frame.rs`).
- Motion score heuristic with documented empirical weights (`motion.rs`).
- BVP STFT implementation (`bvp.rs`).
- Breathing and HR extractors as heuristic experimental modules.
- Welford running-stat baseline pattern (`vitals/anomaly.rs`).
- CRC32 packet finalization pattern (`rv_feature_state.c/h`).

### Experimental / Requires Calibration

- Human presence score from motion heuristics.
- Breathing estimation.
- Heart-rate estimation.
- Fall candidate flags.
- Person count / occupancy count.
- Cross-room and through-wall sensing claims.
- BVP/velocity profile for semantic inference.
- Advanced RuvSense modules: tomography, field model, intention, cross-room, gesture, pose tracker.

### Placeholder / Stub / Mock Observed

- QEMU mock CSI generator (`mock_csi.c/h`) — useful for tests only.
- ESP-IDF host stubs under `test/stubs` — test-only.
- C6/TWT/time-sync no-op stubs on non-C6 targets.
- NDP frame injection TODO/placeholder in `csi_collector.c/h`.
- `adaptive_controller.c` comments show placeholder until Layer 4 features emitted.
- `calibration_proof_runner.rs` contains placeholder proof hash.
- `cir_proof_runner.rs` references placeholder hashes.
- Some 802.11bf DMG/EDMG types are minimal stubs.
- `field_model.rs` has NotCalibrated fallback behavior.

---

## Protocol Lessons for Yugoef

RuView ADR-018 is a good base but lacks fields requested by Yugoef target architecture:

| Requirement | RuView ADR-018 | Yugoef Decision |
|---|---|---|
| magic | Yes: `0xC5110001` | Use Yugoef magic to avoid confusion, or support ADR-018 adapter. |
| protocol_version | Implicit through magic/ADR | Add explicit `protocol_version`. |
| message_type | Sibling magics by packet type | Add explicit message type enum. |
| node_id | u8 | Use string or fixed-length bytes plus numeric short id. |
| boot_id | Missing | Add boot_id. |
| sequence | u32 | Keep u32/u64 sequence. |
| timestamp/uptime | Server timestamp; optional sync packet | Add uptime_ms in raw packet. |
| channel | Frequency MHz | Keep channel/frequency; add WiFi channel number if available. |
| bandwidth | Derived/flags | Include explicit bandwidth. |
| antenna index/count | n_antennas | Keep. |
| subcarrier count | u16 | Keep with validation max. |
| RSSI | i8 | Keep. |
| noise floor | i8 | Keep; optional when unavailable. |
| I/Q samples | int8 pairs | Keep initially. |
| checksum/CRC | Missing in raw CSI | Add CRC32. |
| heartbeat/config | Sibling packets / NVS | Define Yugoef message types. |

Recommended Yugoef approach:

1. Implement **Yugoef protocol v1** with explicit magic/version/type/CRC.
2. Implement **ADR-018 compatibility parser** so RuView-like test data can be ingested.
3. Keep HTTP JSON ingestion for demo/backward compatibility but route real CSI through binary parser.

---

## Signal Processing Lessons for Yugoef

Minimal deterministic pipeline to adapt:

1. Validate packet and metadata.
2. Convert I/Q to amplitude and phase:
   - `amplitude = sqrt(I² + Q²)`
   - `phase = atan2(Q, I)`
3. Reject non-finite values.
4. Per-node sliding window.
5. Phase unwrap across subcarriers/time.
6. Simple outlier filtering/Hampel-like guard.
7. Feature extraction:
   - RSSI
   - noise floor
   - packet loss
   - amplitude mean/variance
   - phase variance
   - motion energy
   - subcarrier coherence
   - signal quality
8. Rolling baseline using Welford/EWMA/MAD.
9. Deterministic semantic event mapping.

Do not adopt first-pass:

- Deep pose estimation.
- Person count claims.
- Medical vitals as production features.
- RuVector/RuField/Cognitum dependencies.
- Full edge-processing packet family.
- Advanced tomography/intention modules.

---

## License and Attribution

RuView root license is MIT (`LICENSE`). If Yugoef adapts protocol ideas, algorithm names, or code structure, add attribution in docs:

> Portions of the ESP32 CSI packet design and signal-processing approach were informed by RuView (https://github.com/ruvnet/RuView), MIT License. Yugoef implements an independent Python/ESP-IDF subset and does not vendor RuView or require Cognitum.

Avoid direct code copy unless license headers and attribution are preserved.

---

## Recommendation for Yugoef

### Adapt

- Binary CSI packet validation concepts.
- I/Q parsing and amplitude/phase formulas.
- Sliding window feature extraction.
- Motion/presence score as heuristic.
- Welford/EWMA baseline methods.
- CRC32 packet integrity.
- Test fixtures for valid/truncated/invalid packets.

### Rewrite Based on Reference

- ESP32 firmware minimal CSI node.
- Python parser for Yugoef protocol + ADR-018 adapter.
- Python DSP feature pipeline.
- Python anomaly engine with semantic events.
- AI provider abstraction and Qwen structured JSON validation.

### Defer

- Breathing/heart rate production output.
- Fall detection production output.
- Person count.
- Cross-room inference.
- BVP/gesture/pose/tomography.
- 802.11bf advanced negotiation.

### Do Not Use as Mandatory Dependency

- Cognitum hardware/software.
- RuVector/RuField crates.
- RuView full firmware stack.
- RuView archive v1 service.
- On-device WASM/mmWave/swarm modules.

---

## Risks if Adapted Incorrectly

1. **False safety claims:** breathing/HR/fall detection can be misleading without validation.
2. **Packet ambiguity:** using RuView magic without attribution/schema can confuse interoperability.
3. **Unbounded storage:** raw CSI volume is high; retention must be enforced.
4. **UDP reliability:** loss/out-of-order is normal and must be measured.
5. **Calibration dependency:** presence/motion thresholds are room-specific.
6. **Sample-rate dependency:** vitals and BVP algorithms break if sampling is irregular.
7. **Security:** raw UDP ingestion must validate size and source; no unbounded queues.
8. **License:** direct copied code requires license preservation.

---

## Conclusion

RuView provides valuable technical reference for Yugoef, especially the ESP32 CSI binary frame design, parser validation, amplitude/phase conversion, and deterministic heuristic signal processing. It should not be used as a direct dependency or copied wholesale. Yugoef should implement a smaller cloud-first pipeline with explicit protocol versioning, bounded storage, conservative event semantics, Qwen only for explanation of structured semantic events, and clear labels for heuristic/experimental features.
