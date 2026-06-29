#!/usr/bin/env python3
"""Replay synthetic Yugoef CSI fixture packets to UDP server.

Fixtures are SYNTHETIC TEST DATA, NOT CAPTURED FROM A REAL PERSON,
and NOT HARDWARE-VALIDATED.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yugoef.protocol import parse_packet, serialize_packet


def rewrite_sequence(packet_bytes: bytes, sequence: int) -> bytes:
    packet = parse_packet(packet_bytes)
    header = packet.header
    header.sequence = sequence & 0xFFFFFFFF
    return serialize_packet(header, packet.payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Yugoef CSI binary fixture over UDP")
    parser.add_argument("--fixture", required=True, help="Path to .bin fixture")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--rate", type=float, default=20.0, help="packets per second")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--start-sequence", type=int, default=None)
    parser.add_argument("--loss-every", type=int, default=0, help="drop every Nth packet")
    parser.add_argument("--duplicate-every", type=int, default=0, help="duplicate every Nth packet")
    parser.add_argument("--out-of-order", action="store_true", help="send one packet with older sequence")
    parser.add_argument("--offline-after", type=int, default=0, help="stop after N sends to simulate offline")
    args = parser.parse_args()

    fixture = Path(args.fixture).read_bytes()
    base = parse_packet(fixture)
    sequence = base.header.sequence if args.start_sequence is None else args.start_sequence
    interval = 1.0 / args.rate if args.rate > 0 else 0.0
    sent = 0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for i in range(args.count):
            if args.offline_after and sent >= args.offline_after:
                break
            current_sequence = sequence + i
            if args.out_of_order and i == args.count // 2:
                current_sequence = max(0, current_sequence - 2)
            if args.loss_every and (i + 1) % args.loss_every == 0:
                time.sleep(interval)
                continue
            packet = rewrite_sequence(fixture, current_sequence)
            sock.sendto(packet, (args.host, args.port))
            sent += 1
            if args.duplicate_every and (i + 1) % args.duplicate_every == 0:
                sock.sendto(packet, (args.host, args.port))
                sent += 1
            time.sleep(interval)
    print(f"sent={sent} fixture={args.fixture} target={args.host}:{args.port}")


if __name__ == "__main__":
    main()
