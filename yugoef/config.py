"""Configuration loader for Yugoef AI agent.

Priority: env vars > config files > defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class QwenConfig:
    """Qwen Cloud API configuration."""

    api_key: str = ""
    base_url: str = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen3.7-plus"  # qwen3.7-plus, qwen-plus, qwen-max, qwen-turbo
    max_tokens: int = 1024
    temperature: float = 0.3

    @classmethod
    def from_env(cls) -> "QwenConfig":
        return cls(
            api_key=os.environ.get("QWEN_API_KEY", ""),
            base_url=os.environ.get(
                "QWEN_BASE_URL", "https://portal.qwen.ai/v1"
            ),
            model=os.environ.get("QWEN_MODEL", "qwen-plus"),
            max_tokens=int(os.environ.get("QWEN_MAX_TOKENS", "1024")),
            temperature=float(os.environ.get("QWEN_TEMPERATURE", "0.3")),
        )


@dataclass
class RuViewConfig:
    """RuView connection configuration."""

    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    sensing_api_url: str = "http://localhost:8080"
    ws_url: str = "ws://localhost:8765/ws/sensing"
    simulated: bool = True  # True = use simulated data (no ESP32 needed)

    @classmethod
    def from_env(cls) -> "RuViewConfig":
        return cls(
            mqtt_broker=os.environ.get("RUVIEW_MQTT_BROKER", "localhost"),
            mqtt_port=int(os.environ.get("RUVIEW_MQTT_PORT", "1883")),
            mqtt_username=os.environ.get("RUVIEW_MQTT_USERNAME"),
            mqtt_password=os.environ.get("RUVIEW_MQTT_PASSWORD"),
            sensing_api_url=os.environ.get(
                "RUVIEW_API_URL", "http://localhost:8080"
            ),
            ws_url=os.environ.get(
                "RUVIEW_WS_URL", "ws://localhost:8765/ws/sensing"
            ),
            simulated=os.environ.get("RUVIEW_SIMULATED", "true").lower()
            == "true",
        )


@dataclass
class ServerConfig:
    """FastAPI server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            host=os.environ.get("YUGOEF_HOST", "0.0.0.0"),
            port=int(os.environ.get("YUGOEF_PORT", "8000")),
            debug=os.environ.get("YUGOEF_DEBUG", "false").lower() == "true",
        )


@dataclass
class CsiConfig:
    """Cloud CSI ingestion configuration."""

    udp_enabled: bool = False
    udp_host: str = "0.0.0.0"
    udp_port: int = 5005
    max_packet_size: int = 1400
    queue_maxsize: int = 4096
    queue_drop_policy: str = "drop_oldest"
    node_timeout_seconds: int = 15

    @classmethod
    def from_env(cls) -> "CsiConfig":
        return cls(
            udp_enabled=os.environ.get("CSI_UDP_ENABLED", "false").lower() == "true",
            udp_host=os.environ.get("CSI_UDP_HOST", "0.0.0.0"),
            udp_port=int(os.environ.get("CSI_UDP_PORT", "5005")),
            max_packet_size=int(os.environ.get("CSI_MAX_PACKET_SIZE", "1400")),
            queue_maxsize=int(os.environ.get("CSI_QUEUE_MAXSIZE", "4096")),
            queue_drop_policy=os.environ.get("CSI_QUEUE_DROP_POLICY", "drop_oldest"),
            node_timeout_seconds=int(os.environ.get("CSI_NODE_TIMEOUT_SECONDS", "15")),
        )


@dataclass
class AppConfig:
    """Top-level application configuration."""

    qwen: QwenConfig = field(default_factory=QwenConfig.from_env)
    ruview: RuViewConfig = field(default_factory=RuViewConfig.from_env)
    server: ServerConfig = field(default_factory=ServerConfig.from_env)
    csi: CsiConfig = field(default_factory=CsiConfig.from_env)

    @classmethod
    def load(cls) -> "AppConfig":
        return cls()
