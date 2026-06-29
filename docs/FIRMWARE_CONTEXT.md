# Yugoef ESP32 Firmware Context

This document gives local firmware-build context for the current Yugoef project state.

## Current project status

Yugoef cloud/backend already supports the CSI fixture pipeline:

```text
Yugoef CSI Protocol v1
→ UDP ingestion
→ bounded queue
→ signal processing
→ deterministic feature extraction
```

The ESP32 firmware now targets that cloud pipeline directly.

## Firmware goal

The firmware is responsible only for WiFi CSI capture and transport:

```text
ESP32 WiFi CSI callback
→ signed int8 I/Q payload
→ Yugoef CSI Protocol v1 binary header
→ CRC32
→ UDP datagram
→ Yugoef backend
```

The ESP32 must not run AI logic.

The ESP32 must not store:

- Qwen API key.
- Backend database credentials.
- User secrets beyond local WiFi SSID/password.

## Default cloud target

Default firmware config points to the Alibaba/Tailscale backend:

```text
YUGOEF_UDP_HOST=100.119.129.28
YUGOEF_UDP_PORT=5005
```

This only works if the ESP32 network can route to `100.119.129.28`.

Important: ESP32 does not run Tailscale itself. If the ESP32 is on a normal LAN, it cannot reach a Tailscale-only IP unless one of these is true:

1. The WiFi router routes Tailscale subnet traffic through a Tailscale subnet router.
2. A laptop/edge machine on the same LAN forwards UDP `5005` to Alibaba.
3. The backend is exposed through a reachable public/VPN endpoint.
4. You temporarily set `YUGOEF_UDP_HOST` to a local backend IP for testing.

## Recommended local test path

Before testing Alibaba routing, validate firmware with a local backend on the same WiFi LAN.

On laptop/backend machine:

```bash
git clone https://github.com/Nayerim-AI/yugoef
cd yugoef
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
export CSI_UDP_ENABLED=true
export CSI_UDP_HOST=0.0.0.0
export CSI_UDP_PORT=5005
uvicorn yugoef.main:app --host 0.0.0.0 --port 8000
```

Find laptop LAN IP:

```bash
ip addr
```

Then set firmware `Yugoef UDP Backend Host` to that LAN IP via:

```bash
cd firmware/esp32-idf
idf.py menuconfig
```

## Alibaba cloud test path

On Alibaba server, pull latest code and run backend with UDP enabled:

```bash
cd /opt/yugoef
git pull origin main
export CSI_UDP_ENABLED=true
export CSI_UDP_HOST=0.0.0.0
export CSI_UDP_PORT=5005
export CSI_MAX_PACKET_SIZE=1400
export CSI_QUEUE_MAXSIZE=4096
export CSI_QUEUE_DROP_POLICY=drop_oldest
export CSI_NODE_TIMEOUT_SECONDS=15
systemctl restart yugoef
```

If the systemd service does not yet include these env vars, add them to `/opt/yugoef/.env` or the service environment, then restart.

Check backend:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/status
curl http://127.0.0.1:8000/metrics
```

Expected after ESP32 starts sending:

```text
packets_received increases
valid_packets increases
online_nodes >= 1
queue_depth changes
```

## Firmware configuration

Path:

```bash
firmware/esp32-idf
```

Configure:

```bash
idf.py set-target esp32
idf.py menuconfig
```

Menu:

```text
Yugoef ESP32 CSI Configuration
├── WiFi SSID
├── WiFi Password
├── Yugoef UDP Backend Host
├── Yugoef UDP Backend Port
├── Yugoef numeric node ID
├── Yugoef numeric room ID
├── Expected WiFi channel
├── CSI max packet size
└── Heartbeat interval milliseconds
```

Default values:

```text
Yugoef UDP Backend Host = 100.119.129.28
Yugoef UDP Backend Port = 5005
Yugoef numeric node ID = 1
Yugoef numeric room ID = 1
Expected WiFi channel = 6
CSI max packet size = 1400
Heartbeat interval milliseconds = 5000
```

## Build and flash

```bash
cd firmware/esp32-idf
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Alternative serial port:

```bash
idf.py -p /dev/ttyACM0 flash monitor
```

## Expected ESP32 logs

```text
Yugoef ESP32 CSI firmware boot_id=...
WiFi STA started. Connecting to SSID: ...
Got IP: ...
UDP target 100.119.129.28:5005
CSI callback enabled
heartbeat sent, csi_sent=..., csi_dropped=...
```

## Protocol packets sent by firmware

- `NODE_HELLO` after WiFi/UDP init.
- `RAW_CSI` from ESP-IDF CSI callback.
- `HEARTBEAT` every configured interval.

Header follows `docs/PROTOCOL.md`:

```text
magic = 0x59474631
protocol_version = 1
header_length = 40
endianness = big-endian
payload = signed int8 I/Q bytes
crc32 = IEEE CRC32 over header without CRC + payload
```

## Safety and limitations

Current firmware/backend integration is for technical validation.

Not yet supported:

- Breathing estimation.
- Heart-rate estimation.
- Fall detection.
- Person counting.
- Distress detection.
- Medical or safety-critical inference.

The backend feature extraction is deterministic and heuristic. It is not calibrated for a real room until real CSI captures and ground-truth evaluation are collected.
