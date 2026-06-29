# ESP32 Local Upload Guide — Yugoef CSI v1

This guide is for local ESP-IDF flashing of the Yugoef ESP32 CSI firmware.

## Status

The firmware sends binary Yugoef CSI Protocol v1 packets over UDP:

```text
ESP32 CSI callback
→ RAW_CSI protocol v1 packet
→ UDP datagram
→ Yugoef backend CSI ingestion
```

No AI key is stored on ESP32. No Qwen call is made from firmware.

## Backend prerequisite

Run Yugoef backend with UDP ingestion enabled:

```bash
export CSI_UDP_ENABLED=true
export CSI_UDP_HOST=0.0.0.0
export CSI_UDP_PORT=5005
export CSI_MAX_PACKET_SIZE=1400
export CSI_QUEUE_MAXSIZE=4096
export CSI_QUEUE_DROP_POLICY=drop_oldest
export CSI_NODE_TIMEOUT_SECONDS=15
uvicorn yugoef.main:app --host 0.0.0.0 --port 8000
```

Check metrics:

```bash
curl http://127.0.0.1:8000/metrics
```

## Firmware path

```bash
cd firmware/esp32-idf
```

## Configure

```bash
idf.py menuconfig
```

Set:

```text
Yugoef ESP32 CSI Configuration
├── WiFi SSID
├── WiFi Password
├── Yugoef UDP Backend Host
├── Yugoef UDP Backend Port = 5005
├── Yugoef numeric node ID
├── Yugoef numeric room ID
├── Expected WiFi channel
├── CSI max packet size = 1400
└── Heartbeat interval milliseconds = 5000
```

For backend on Alibaba/Tailscale, set `Yugoef UDP Backend Host` to the backend Tailscale IP reachable from the ESP32 network only if routed. For same LAN testing, use the local machine LAN IP.

## Build

```bash
idf.py set-target esp32
idf.py build
```

## Flash and monitor

Replace port as needed:

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

Useful monitor logs:

```text
Yugoef ESP32 CSI firmware boot_id=...
WiFi STA started...
Got IP: ...
UDP target ...:5005
CSI callback enabled
heartbeat sent, csi_sent=..., csi_dropped=...
```

## Backend verification

While firmware runs:

```bash
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/v1/status
```

Expected metric changes:

```text
packets_received increases
valid_packets increases
online_nodes >= 1
queue_depth may increase
```

## Protocol mapping

Firmware sends:

- `NODE_HELLO` once after WiFi/UDP init.
- `RAW_CSI` from ESP-IDF CSI callback.
- `HEARTBEAT` periodically.

Header follows `docs/PROTOCOL.md`:

```text
magic = 0x59474631
protocol_version = 1
header_length = 40
endianness = big-endian
payload = signed int8 I/Q bytes from ESP-IDF CSI buffer
crc32 = IEEE CRC32 over header without CRC + payload
```

## Known limitations

- Not yet calibrated for real room layout.
- CSI payload shape depends on ESP-IDF/ESP32 WiFi mode and AP capabilities.
- Noise floor currently uses deterministic fallback `-95 dBm`.
- Antenna metadata is fixed to single antenna.
- Data is hardware-originated after flashing, but activity/presence scoring is still heuristic.
- No breathing, heart-rate, fall detection, person counting, medical, or safety-critical inference.
