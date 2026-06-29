# Yugoef UDP CSI Authentication

UDP `5005` can be exposed publicly only when packet authentication is enabled.

## Mechanism

Yugoef CSI Protocol v1 supports an authenticated-packet flag:

```text
flags bit 0 = authenticated packet
```

When `CSI_AUTH_SECRET` is configured on the backend, every UDP CSI packet must include an HMAC-SHA256 authentication tag.

The firmware computes:

```text
hmac = HMAC-SHA256(YUGOEF_NODE_SECRET, header_without_crc + raw_payload)
auth_tag = first 16 bytes of hmac
wire_payload = raw_payload + auth_tag
crc32 = CRC32(header_without_crc + wire_payload)
```

The backend validates:

1. CRC32.
2. Auth flag present.
3. HMAC tag matches `CSI_AUTH_SECRET`.
4. RAW_CSI payload length after removing tag.

Unsigned packets are rejected when `CSI_AUTH_SECRET` is non-empty.

## Backend config

Set on Alibaba `/opt/yugoef/.env`:

```text
CSI_UDP_ENABLED=true
CSI_UDP_HOST=0.0.0.0
CSI_UDP_PORT=5005
CSI_AUTH_SECRET=<same-secret-as-firmware>
```

Do not commit the real secret.

## Firmware config

Set in ESP-IDF menuconfig:

```text
Yugoef ESP32 CSI Configuration
└── Yugoef node auth secret = <same-secret-as-backend>
```

Kconfig symbol:

```text
CONFIG_YUGOEF_NODE_SECRET
```

## Public UDP warning

If Alibaba public IP `47.236.18.24:5005` is opened, use a strong random secret. The default `change-me-yugoef-node-secret` is for local development only.

Recommended:

```bash
openssl rand -hex 32
```

Use that value for both backend `CSI_AUTH_SECRET` and firmware `YUGOEF_NODE_SECRET`.

## Firmware target

For direct public cloud mode:

```text
YUGOEF_UDP_HOST=47.236.18.24
YUGOEF_UDP_PORT=5005
```

For Tailscale-only mode:

```text
YUGOEF_UDP_HOST=100.119.129.28
YUGOEF_UDP_PORT=5005
```

ESP32 normally cannot reach Tailscale IP directly unless the WiFi network has routing to Tailscale.
