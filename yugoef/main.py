"""Yugoef FastAPI server.

Endpoints:
- POST /v1/analyze — Analyze a single RuView sensing event
- POST /v1/trend — Trend analysis from event history
- POST /v1/detect/anomaly — Anomaly detection
- GET /health — Health check
- GET /v1/status — Agent status summary
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ai_agent import YugoefAgent
from .config import AppConfig
from .ingestion import CsiIngestionService, CsiUdpServer, DropPolicy, IngestionConfig, UdpServerConfig

log = logging.getLogger(__name__)

# ── Request/Response models ──────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """Single RuView sensing event to analyze."""

    event: dict[str, Any]
    history: Optional[list[dict[str, Any]]] = None


class AnalyzeResponse(BaseModel):
    """AI analysis result."""

    analysis: Optional[str] = None
    anomaly: Optional[str] = None
    trend: Optional[str] = None
    model_used: str = ""


class TrendRequest(BaseModel):
    """Batch of events for trend analysis."""

    events: list[dict[str, Any]]


class AnomalyRequest(BaseModel):
    """Event + history for anomaly detection."""

    event: dict[str, Any]
    history: list[dict[str, Any]]


# ── App lifecycle ────────────────────────────────────────────────────

config = AppConfig.load()
agent: Optional[YugoefAgent] = None
csi_service = CsiIngestionService(
    IngestionConfig(
        max_packet_size=config.csi.max_packet_size,
        queue_maxsize=config.csi.queue_maxsize,
        drop_policy=DropPolicy(config.csi.queue_drop_policy),
        node_timeout_seconds=config.csi.node_timeout_seconds,
        auth_secret=config.csi.auth_secret,
    )
)
csi_udp_server: Optional[CsiUdpServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, csi_udp_server
    agent = YugoefAgent(config)
    if config.csi.udp_enabled:
        csi_udp_server = CsiUdpServer(
            csi_service,
            UdpServerConfig(host=config.csi.udp_host, port=config.csi.udp_port),
        )
        await csi_udp_server.start()
    log.info("Yugoef server started — Qwen model: %s", config.qwen.model)
    yield
    if csi_udp_server:
        await csi_udp_server.stop()
    if agent:
        await agent.qwen.close()
    log.info("Yugoef server stopped")


app = FastAPI(
    title="Yugoef — Room Intelligence Agent",
    version="0.1.0",
    description="Turn RuView WiFi sensing data into AI-powered room intelligence",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Endpoints ────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "ok", "model": config.qwen.model}


@app.get("/metrics")
async def metrics():
    """CSI ingestion metrics."""
    csi_service.online_nodes
    return csi_service.metrics.as_dict()


@app.get("/v1/status")
async def status():
    """Agent status."""
    if not agent:
        raise HTTPException(503, "Agent not initialized")
    return {
        "agent": "Yugoef",
        "model": config.qwen.model,
        "simulated": config.ruview.simulated,
        "event_buffer": len(agent.consumer.recent_events),
        "csi_udp_enabled": config.csi.udp_enabled,
        "csi_queue_depth": csi_service.metrics.queue_depth,
        "online_nodes": csi_service.online_nodes,
    }


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze_event(req: AnalyzeRequest):
    """Analyze a single RuView sensing event with Qwen Cloud."""
    if not agent:
        raise HTTPException(503, "Agent not initialized")

    try:
        analysis = await agent.qwen.analyze_room_event(req.event)
        result: dict[str, Any] = {
            "analysis": analysis,
            "anomaly": None,
            "trend": None,
            "model_used": config.qwen.model,
        }

        # Optional anomaly check
        if req.history:
            anomaly = await agent.qwen.detect_anomaly(req.event, req.history)
            result["anomaly"] = anomaly

        # Optional trend from history
        if req.history and len(req.history) >= 3:
            trend = await agent.qwen.summarize_trend(req.history)
            result["trend"] = trend

        return AnalyzeResponse(**result)

    except Exception as e:
        log.error("Analysis failed: %s", e)
        raise HTTPException(500, f"Analysis failed: {e}")


@app.post("/v1/trend")
async def analyze_trend(req: TrendRequest):
    """Generate trend summary from event history."""
    if not agent:
        raise HTTPException(503, "Agent not initialized")
    try:
        trend = await agent.qwen.summarize_trend(req.events)
        return {"trend": trend, "events_analyzed": len(req.events)}
    except Exception as e:
        raise HTTPException(500, f"Trend analysis failed: {e}")


@app.post("/v1/detect/anomaly")
async def detect_anomaly(req: AnomalyRequest):
    """Check for anomalies in current event vs history."""
    if not agent:
        raise HTTPException(503, "Agent not initialized")
    try:
        anomaly = await agent.qwen.detect_anomaly(req.event, req.history)
        return {"anomaly": anomaly}
    except Exception as e:
        raise HTTPException(500, f"Anomaly detection failed: {e}")


@app.post("/v1/ingest")
async def ingest_event(req: AnalyzeRequest):
    """Ingest a RuView event and add to agent's buffer.
    Returns minimal acknowledgement — AI analysis is async.

    Use this for streaming integration where the agent
    should track events over time.
    """
    if not agent:
        raise HTTPException(503, "Agent not initialized")

    # Add to buffer
    agent.consumer._buffer.append(req.event)  # type: ignore[attr-defined]
    if len(agent.consumer._buffer) > 100:  # type: ignore[attr-defined]
        agent.consumer._buffer.pop(0)  # type: ignore[attr-defined]

    return {
        "ingested": True,
        "buffer_size": len(agent.consumer.recent_events),
        "message": "Event stored for context. Use /v1/analyze for AI analysis.",
    }


# ── CLI entry point ──────────────────────────────────────────────────


def serve() -> None:
    """Entry point: `yugoef-serve` CLI command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run(
        "yugoef.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
    )


if __name__ == "__main__":
    serve()
