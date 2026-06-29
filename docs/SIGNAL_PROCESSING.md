# Yugoef Cloud CSI Signal Processing

**Status:** Implemented for synthetic binary fixtures. Not hardware-validated.

## Data Notice

```text
SYNTHETIC TEST DATA
NOT CAPTURED FROM A REAL PERSON
NOT HARDWARE-VALIDATED
```

## Pipeline

```text
Raw I/Q payload
→ int8 I/Q decoding
→ amplitude
→ wrapped phase
→ phase unwrap
→ bounded sliding window by node/boot/channel/antenna
→ effective sample-rate calculation
→ missing-frame detection
→ top-K active subcarrier selection
→ subcarrier coherence
```

## Formulas

```text
amplitude = sqrt(I² + Q²)
phase = atan2(Q, I)
```

Phase unwrap adds/subtracts `2π` when adjacent phase delta crosses `±π`.

## State Key

Signal state is separated by:

```text
(node_id, boot_id, wifi_channel, antenna_index)
```

A boot reset or channel change creates a new bounded window.

## Bounds

- Window length is configured in `CsiSignalPipeline(window_size=...)`.
- Buffers are bounded deques.
- The protocol parser enforces packet-size and subcarrier bounds before signal processing.

## Deferred

Not implemented in this phase:

- Heart rate.
- Breathing.
- Fall detection.
- Person counting.
- Medical or safety-critical interpretation.

Those require real CSI data, calibration, and ground-truth evaluation.
