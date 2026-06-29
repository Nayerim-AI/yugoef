# Yugoef CSI Protocol v1

**Status:** Implemented for cloud/backend parser, serializer, and tests.  
**Scope:** Synthetic binary fixtures and cloud pipeline. ESP32 firmware is not implemented in this phase.

---

## Safety and Data Status

Protocol tests use:

```text
SYNTHETIC TEST DATA
NOT CAPTURED FROM A REAL PERSON
NOT HARDWARE-VALIDATED
```

This protocol does not imply medical, safety-critical, fall-detection, breathing, heart-rate, or person-counting readiness.

---

## Design Goals

- Fixed-width integers.
- Explicit big-endian byte order.
- No native struct alignment.
- Signed `int8` I/Q samples.
- Payload order: `I0,Q0,I1,Q1,...`.
- CRC32 over header without CRC and payload.
- Explicit packet-size bounds.
- Typed parser errors for malformed packets.
- Sequence tracking by `(node_id, boot_id, message_type)`.

---

## Constants

| Name | Value |
|---|---:|
| Magic | `0x59474631` (`YGF1`) |
| Protocol version | `1` |
| Endianness | Big-endian/network order |
| Header length | `40` bytes |
| CRC length | `4` bytes |
| Max packet size | `1400` bytes |
| Max subcarriers | `256` |
| Max antennas | `4` |

---

## Message Types

| Type | Value | Purpose |
|---|---:|---|
| `NODE_HELLO` | `1` | Node boot/registration announcement. |
| `RAW_CSI` | `2` | Raw CSI I/Q payload. |
| `HEARTBEAT` | `3` | Node liveness and basic RF metadata. |
| `CONFIG` | `4` | Cloud-to-node configuration message, reserved for future use. |
| `CONFIG_ACK` | `5` | Node acknowledgement for config, reserved for future use. |
| `ERROR` | `6` | Node-side error report, reserved for future use. |

---

## Header Layout

All fields are big-endian. Signed fields are two's complement.

| Offset | Size | Field | Type | Notes |
|---:|---:|---|---|---|
| 0 | 4 | `magic` | `u32` | `0x59474631`. |
| 4 | 1 | `protocol_version` | `u8` | Must be `1`. |
| 5 | 1 | `message_type` | `u8` | See message type table. |
| 6 | 1 | `header_length` | `u8` | Must be `40`. |
| 7 | 1 | `flags` | `u8` | Reserved bitfield. |
| 8 | 2 | `node_id` | `u16` | Numeric node id for v1. |
| 10 | 2 | `room_id` | `u16` | Numeric room id for v1. |
| 12 | 4 | `boot_id` | `u32` | Changes after node reboot. |
| 16 | 4 | `sequence` | `u32` | Per `(node_id, boot_id, message_type)`. |
| 20 | 4 | `uptime_ms` | `u32` | Device uptime in milliseconds. |
| 24 | 1 | `wifi_channel` | `u8` | WiFi channel number. |
| 25 | 1 | `bandwidth_mhz` | `u8` | Usually 20/40. |
| 26 | 1 | `antenna_index` | `u8` | Antenna index. |
| 27 | 1 | `antenna_count` | `u8` | `1..4` for RAW_CSI. |
| 28 | 2 | `subcarrier_count` | `u16` | `1..256` for RAW_CSI; `0` for non-CSI messages. |
| 30 | 1 | `rssi_dbm` | `i8` | RSSI in dBm. |
| 31 | 1 | `noise_floor_dbm` | `i8` | Noise floor in dBm. |
| 32 | 2 | `payload_length` | `u16` | Payload byte count. |
| 34 | 2 | `reserved` | `u16` | Must be `0` in serializer. |
| 36 | 4 | `crc32` | `u32` | IEEE CRC32 over bytes `0..35` + payload. |

Payload starts at offset `40`.

---

## RAW_CSI Payload

For `RAW_CSI`, payload must be:

```text
subcarrier_count * antenna_count * 2 bytes
```

Each subcarrier sample is signed int8 pair:

```text
I0,Q0,I1,Q1,I2,Q2,...
```

The cloud signal pipeline computes:

```text
amplitude = sqrt(I² + Q²)
phase = atan2(Q, I)
```

---

## CRC32

CRC input:

```text
header bytes 0..35 + payload bytes
```

CRC field bytes `36..39` are excluded from CRC input.

CRC algorithm:

- IEEE CRC32 compatible with Python `zlib.crc32`.
- Stored as unsigned `u32` big-endian.

---

## Parser Errors

The parser exposes typed errors:

| Error | Meaning |
|---|---|
| `InvalidMagicError` | Magic is not `YGF1`. |
| `UnsupportedVersionError` | Protocol version is not supported. |
| `TruncatedPacketError` | Header or payload is shorter than declared. |
| `InvalidPayloadLengthError` | Payload length does not match packet size or RAW_CSI dimensions. |
| `InvalidSubcarrierCountError` | Subcarrier or antenna count is out of bounds. |
| `CrcMismatchError` | CRC32 validation failed. |
| `InvalidMessageTypeError` | Unknown message type. |
| `PacketTooLargeError` | Packet exceeds configured max size. |

---

## Sequence Tracking

Sequence state is tracked by:

```text
(node_id, boot_id, message_type)
```

Statuses:

| Status | Meaning |
|---|---|
| `FIRST_PACKET` | First packet for this key. |
| `IN_ORDER` | Sequence equals previous + 1. |
| `GAP` | Sequence jumped forward. |
| `DUPLICATE` | Sequence repeated. |
| `OUT_OF_ORDER` | Sequence is older than previous. |
| `NEW_BOOT` | Node id and message type seen before with different boot id. |
| `WRAP_AROUND` | Previous sequence was `0xFFFFFFFF`, new sequence is `0`. |

---

## Current Implementation

Implemented files:

```text
yugoef/protocol/constants.py
yugoef/protocol/errors.py
yugoef/protocol/models.py
yugoef/protocol/parser.py
yugoef/protocol/serializer.py
yugoef/protocol/sequence.py
tests/test_protocol.py
```

Current tests cover:

- serializer/parser round trip
- valid RAW_CSI
- valid HEARTBEAT
- invalid magic
- unsupported version
- truncated header
- truncated payload
- invalid payload length
- invalid subcarrier count
- CRC mismatch
- duplicate sequence
- sequence gap
- out-of-order sequence
- new boot id
- uint32 wrap-around

---

## RuView Attribution

ESP32 CSI packet and signal-processing design were informed by RuView (MIT License). Yugoef implements an independent protocol and parser and does not vendor RuView or require Cognitum.
