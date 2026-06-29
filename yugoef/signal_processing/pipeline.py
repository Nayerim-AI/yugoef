from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from yugoef.protocol import ParsedPacket

from .iq import decode_iq
from .models import SignalFrame, SignalPipelineResult
from .phase import phase_unwrap
from .subcarriers import subcarrier_coherence, top_k_active_subcarriers


WindowKey = tuple[str, int, int, int]


@dataclass
class SignalWindow:
    maxlen: int
    frames: deque[SignalFrame] = field(default_factory=deque)

    def append(self, frame: SignalFrame) -> None:
        self.frames.append(frame)
        while len(self.frames) > self.maxlen:
            self.frames.popleft()


class CsiSignalPipeline:
    def __init__(self, window_size: int = 64, active_subcarrier_k: int = 8) -> None:
        self.window_size = window_size
        self.active_subcarrier_k = active_subcarrier_k
        self.windows: dict[WindowKey, SignalWindow] = {}

    def process(self, packet: ParsedPacket) -> SignalPipelineResult:
        header = packet.header
        samples = decode_iq(packet.payload)
        phases = phase_unwrap([sample.phase for sample in samples])
        frame = SignalFrame(
            node_id=str(header.node_id),
            room_id=header.room_id,
            boot_id=header.boot_id,
            channel=header.wifi_channel,
            antenna_index=header.antenna_index,
            sequence=header.sequence,
            uptime_ms=header.uptime_ms,
            rssi_dbm=header.rssi_dbm,
            noise_floor_dbm=header.noise_floor_dbm,
            amplitudes=[sample.amplitude for sample in samples],
            phases=phases,
        )
        key = (frame.node_id, frame.boot_id, frame.channel, frame.antenna_index)
        window = self.windows.setdefault(key, SignalWindow(maxlen=self.window_size))
        missing = 0
        if window.frames:
            last = window.frames[-1]
            if frame.sequence > last.sequence + 1:
                missing = frame.sequence - last.sequence - 1
        window.append(frame)
        rows = [item.amplitudes for item in window.frames]
        active = top_k_active_subcarriers(rows, self.active_subcarrier_k)
        coherence = subcarrier_coherence(rows)
        return SignalPipelineResult(
            frame=frame,
            window_sample_count=len(window.frames),
            effective_sample_rate_hz=self._effective_sample_rate(window.frames),
            missing_frames=missing,
            active_subcarriers=active,
            subcarrier_coherence=coherence,
        )

    @staticmethod
    def _effective_sample_rate(frames: deque[SignalFrame]) -> float:
        if len(frames) < 2:
            return 0.0
        elapsed_ms = frames[-1].uptime_ms - frames[0].uptime_ms
        if elapsed_ms <= 0:
            return 0.0
        return (len(frames) - 1) / (elapsed_ms / 1000.0)
