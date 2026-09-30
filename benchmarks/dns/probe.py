#!/usr/bin/env python3
"""measure udp dns requests inside the isolated test client"""

from __future__ import annotations

import argparse
import json
import random
import socket
import struct
import sys
import time


def _encode_name(domain: str) -> bytes:
    labels = domain.rstrip(".").split(".")
    return b"".join(bytes([len(label)]) + label.encode("ascii") for label in labels) + b"\x00"


def _skip_name(packet: bytes, offset: int) -> int:
    while True:
        length = packet[offset]
        # compressed names end with a two-byte pointer
        if length & 0xC0 == 0xC0:
            return offset + 2
        offset += 1
        if length == 0:
            return offset
        offset += length


def query(server: str, domain: str, timeout: float = 3.0) -> dict[str, object]:
    query_id = random.SystemRandom().randrange(0, 65536)
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    packet = header + _encode_name(domain) + struct.pack("!HH", 1, 1)
    address = socket.gethostbyname(server)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    started = time.perf_counter()
    try:
        sock.sendto(packet, (address, 53))
        response, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    wall_time_ms = (time.perf_counter() - started) * 1000

    response_id, flags, questions, answers, _, _ = struct.unpack("!HHHHHH", response[:12])
    if response_id != query_id:
        raise ValueError("DNS response ID did not match the request")
    rcode = flags & 0x000F
    offset = 12
    # answers begin after every encoded question name and its type/class pair
    for _ in range(questions):
        offset = _skip_name(response, offset) + 4

    addresses: list[str] = []
    for _ in range(answers):
        offset = _skip_name(response, offset)
        record_type, record_class, _, length = struct.unpack(
            "!HHIH", response[offset : offset + 10]
        )
        offset += 10
        data = response[offset : offset + length]
        offset += length
        if record_type == 1 and record_class == 1 and length == 4:
            addresses.append(socket.inet_ntoa(data))

    if rcode == 3:
        response_class = "nxdomain"
    elif "0.0.0.0" in addresses:
        response_class = "blocked"
    elif addresses:
        response_class = "resolved"
    else:
        response_class = "no-a-answer"
    return {
        "success": rcode == 0,
        "wall_time_ms": wall_time_ms,
        "response_class": response_class,
        "answer_count": len(addresses),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repetitions < 1 or args.repetitions > 50:
        print("repetitions must be between 1 and 50", file=sys.stderr)
        return 2
    results = [query(args.server, args.domain) for _ in range(args.repetitions)]
    if args.json:
        print(json.dumps(results))
    else:
        print(results[-1]["response_class"])
    return 0 if all(result["success"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
