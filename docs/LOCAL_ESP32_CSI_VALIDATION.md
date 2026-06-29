# Local ESP32 CSI Validation Report

Validation date: 2026-06-30 (Asia/Jakarta)

Repository branch: `main`

Validated base commit: `9cf77eb`

Result: **PASS**

This document records the first hardware-validated local ESP32 CSI path and
translates the result into concrete requirements for the future Yugoef cloud
website. It intentionally contains no WiFi password, API key, or other secret.

## 1. Validated data path

```text
ESP32-D0WDQ6
  -> laptop WiFi hotspot (2.4 GHz, channel 6)
  -> Yugoef CSI Protocol v1 over UDP
  -> 10.42.0.1:5005
  -> CsiIngestionService
  -> metrics and node health
```

The laptop kept its existing internet connection through `wlp8s0` while a
second virtual interface, `ap0`, hosted the ESP32 network. The wireless driver
supports one managed interface and one AP interface simultaneously when both
use the same channel.

## 2. Validation evidence

| Area | Result |
|---|---|
| USB adapter | CH340 `1a86:7523` detected |
| Serial port | `/dev/ttyUSB0` |
| ESP32 chip | ESP32-D0WDQ6 revision 1.0 |
| ESP-IDF | v6.0.1 |
| Firmware target | `esp32` |
| Hotspot interface | `ap0` |
| Hotspot address | `10.42.0.1/24` |
| Hotspot radio | 2.4 GHz, channel 6, 20 MHz |
| ESP32 address | `10.42.0.75/24` |
| UDP destination | `10.42.0.1:5005` |
| Backend API | `0.0.0.0:8000` |
| Backend UDP listener | `0.0.0.0:5005` |
| Python tests | `37 passed` |
| Firmware build | Passed |
| Firmware flash | Passed at 115200 baud |
| Packet capture | 20 valid packets, zero capture drops |
| Captured packet types | 18 `RAW_CSI`, 2 `HEARTBEAT` |
| Parsed RAW_CSI shape | 128 subcarriers, 256 payload bytes |
| Node and room | `node_id=1`, `room_id=1` |

Representative serial output:

```text
Got IP: 10.42.0.75
UDP target 10.42.0.1:5005
CSI callback enabled
heartbeat sent, csi_sent=0, csi_dropped=0
heartbeat sent, csi_sent=3, csi_dropped=0
heartbeat sent, csi_sent=14, csi_dropped=0
heartbeat sent, csi_sent=29, csi_dropped=0
```

Representative backend progression:

```text
packets_received: 0 -> 291
valid_packets: 291
invalid_packets: 0
crc_mismatch: 0
queue_drops: 0
queue_depth: 291
online_nodes: 1
```

`online_nodes` remained `1` after waiting longer than the configured 15-second
node timeout, proving that heartbeat packets maintain node liveness.

The project parser independently decoded a captured datagram as:

```text
message_type=HEARTBEAT
node_id=1
room_id=1
wifi_channel=6
packet_bytes=40
parser=valid
```

It also decoded the traffic-generated CSI capture as:

```text
total_valid=20
HEARTBEAT=2
RAW_CSI=18
raw_csi_node_id=1
raw_csi_room_id=1
raw_csi_channel=6
raw_csi_subcarriers=128
raw_csi_payload_bytes=256
parser=valid
```

## 3. Firmware compatibility fixes

Two changes were required for ESP-IDF v6.0.1:

1. `WIFI_BW_HT20` and `WIFI_BW_HT40` were replaced by the current
   `WIFI_BW20` and `WIFI_BW40` enum values.
2. `CONFIG_ESP_WIFI_CSI_ENABLED=y` was added to `sdkconfig.defaults`.

Without the CSI feature flag, the firmware compiled but
`esp_wifi_set_csi_config()` returned `ESP_FAIL`, causing a reboot loop through
`ESP_ERROR_CHECK`. Enabling the feature flag removed the crash and activated
the callback. No protocol bytes or field definitions were changed.

The CH340 link was unreliable at the default 460800 flash baud. Flashing at
115200 succeeded and verified every written image hash.

## 4. Reproduction outline

Use a local `sdkconfig` for credentials. Do not add that file to Git.

```bash
source /home/midory-it/.espressif/v6.0.1/esp-idf/export.sh
cd firmware/esp32-idf
idf.py set-target esp32
idf.py menuconfig
```

Required firmware values:

```text
WiFi SSID               = <LOCAL_2G_HOTSPOT_SSID>
WiFi Password           = <LOCAL_HOTSPOT_PASSWORD>
Yugoef UDP Backend Host = <LOCAL_BACKEND_IP>
Yugoef UDP Backend Port = 5005
Yugoef numeric node ID  = 1
Yugoef numeric room ID  = 1
Expected WiFi channel   = <HOTSPOT_CHANNEL>
CSI max packet size     = 1400
Heartbeat interval      = 5000 ms
```

Build and flash:

```bash
idf.py fullclean
idf.py build
idf.py -p /dev/ttyUSB0 -b 115200 flash monitor
```

Backend runtime configuration:

```bash
export CSI_UDP_ENABLED=true
export CSI_UDP_HOST=0.0.0.0
export CSI_UDP_PORT=5005
export CSI_MAX_PACKET_SIZE=1400
export CSI_QUEUE_MAXSIZE=4096
export CSI_QUEUE_DROP_POLICY=drop_oldest
export CSI_NODE_TIMEOUT_SECONDS=15

source .venv/bin/activate
PYTHONPATH="$PWD" uvicorn yugoef.main:app --host 0.0.0.0 --port 8000
```

Validation commands:

```bash
ss -lunp | grep ':5005'
ss -ltnp | grep ':8000'
curl -s http://127.0.0.1:8000/metrics
curl -s http://127.0.0.1:8000/v1/status
```

## 5. Current website-facing API

The current FastAPI application exposes:

| Method | Path | Current website use |
|---|---|---|
| `GET` | `/health` | API availability and model name |
| `GET` | `/metrics` | CSI operational counters |
| `GET` | `/v1/status` | Agent, queue, simulation, and online-node summary |
| `POST` | `/v1/analyze` | AI explanation for one structured sensing event |
| `POST` | `/v1/trend` | AI summary over event history |
| `POST` | `/v1/detect/anomaly` | AI anomaly comparison |
| `POST` | `/v1/ingest` | Add a structured event to the in-memory context buffer |

Example `/metrics` response:

```json
{
  "packets_received": 291,
  "valid_packets": 291,
  "invalid_packets": 0,
  "crc_mismatch": 0,
  "duplicate_packets": 0,
  "out_of_order_packets": 0,
  "sequence_gaps": 0,
  "queue_drops": 0,
  "queue_depth": 291,
  "online_nodes": 1
}
```

Example `/v1/status` response shape:

```json
{
  "agent": "Yugoef",
  "model": "qwen-plus",
  "simulated": true,
  "event_buffer": 0,
  "csi_udp_enabled": true,
  "csi_queue_depth": 291,
  "online_nodes": 1
}
```

These endpoints are enough for an initial operational status page. They are
not yet enough for a complete room dashboard because node details, historical
features, room state, and live updates are not exposed over HTTP or WebSocket.

## 6. Recommended cloud website information architecture

### Overview

- Online/offline node count.
- Active room count.
- Packet throughput and valid-packet rate.
- Invalid packet, CRC, sequence-gap, and queue-drop alerts.
- Current AI summary and latest anomaly.

### Rooms

- Room name and numeric `room_id`.
- Presence state, motion level, confidence, and signal quality.
- Last update time and data-source badge: live or simulated.
- Small trend chart for motion/presence features.

### Node detail

- `node_id`, `room_id`, online state, boot ID, and last seen.
- Firmware version, WiFi channel, RSSI, noise floor, and packet rate.
- CSI quality diagnostics and sequence health.
- Reboot/boot-ID history.

### Events and alerts

- Chronological structured sensing events.
- Anomaly severity, acknowledgement, and resolution state.
- Filters by room, node, time range, and event type.

### AI insights

- Current Qwen explanation.
- Trend summary and evidence window.
- Model used, generation time, and failure state.
- Clear distinction between measured features and AI interpretation.

### System health

- UDP listener and API availability.
- Queue depth/capacity and queue drops.
- Packet validity and CRC error rate.
- Last heartbeat per node.
- Cloud worker, database, and Qwen API health.

## 7. API additions needed for the website

The following endpoints are recommendations, not current implementation:

```text
GET  /v1/nodes
GET  /v1/nodes/{node_id}
GET  /v1/rooms
GET  /v1/rooms/{room_id}/latest
GET  /v1/rooms/{room_id}/timeseries?from=&to=&bucket=
GET  /v1/events?room_id=&node_id=&from=&to=
GET  /v1/alerts
POST /v1/alerts/{alert_id}/acknowledge
WS   /v1/ws/dashboard
```

Suggested node response:

```json
{
  "node_id": "1",
  "room_id": 1,
  "online": true,
  "last_seen": "2026-06-30T00:15:57+07:00",
  "boot_id": 2373267161,
  "last_message_type": "HEARTBEAT",
  "wifi_channel": 6,
  "rssi_dbm": -31,
  "noise_floor_dbm": -95,
  "packet_rate_hz": 20.0,
  "firmware_version": "unknown"
}
```

The backend already maintains most liveness fields in `NodeHealth`, but only
the aggregate online count is public. A read-only node endpoint is the smallest
useful next backend change for the website.

## 8. Cloud pipeline work still required

1. Add a consumer that drains the bounded CSI queue continuously.
2. Run deterministic CSI feature extraction on `RAW_CSI` packets.
3. Aggregate features into stable room-state windows.
4. Persist node health, features, events, alerts, and AI analyses.
5. Expose node, room, history, and live-stream APIs.
6. Add authentication and role-based authorization.
7. Restrict CORS to the deployed website origin.
8. Put the HTTP API behind TLS/reverse proxy; do not expose the development
   Uvicorn server directly.
9. Restrict UDP 5005 to known edge source addresses or a private overlay
   network when cloud routing is introduced.
10. Add retention limits so raw CSI does not become an unbounded cloud data
    store. Prefer structured features for long-term storage.

The current queue is bounded at 4096 items with `drop_oldest`, but during this
validation no production consumer drained it. A cloud deployment must add the
consumer before sustained CSI traffic is enabled.

## 9. Privacy and product boundaries

- Present CSI-derived results as room-state estimates, not direct observation.
- Keep raw CSI at the edge where practical; send compact structured features
  to the cloud for dashboard history and Qwen reasoning.
- Never label the current prototype as medical, safety-critical, or a verified
  vital-sign monitor.
- Show confidence, freshness, and simulated/live provenance in the UI.
- Never expose WiFi credentials, Qwen keys, or private infrastructure addresses
  through frontend bundles or public API responses.

## 10. Definition of done for the first cloud dashboard

- At least one real node appears online from heartbeat data.
- Node detail shows last seen, room, RSSI, and packet health.
- Room page shows latest deterministic features and freshness.
- Dashboard receives live updates without aggressive polling.
- Historical data survives backend restart.
- Queue remains below capacity under expected packet rate.
- Invalid packets and node timeout produce visible operational alerts.
- Browser access uses HTTPS and authenticated API calls.
- No raw credential or API secret is present in repository history or frontend
  artifacts.
