#!/usr/bin/env python3
"""bridge an internal TCP listener to the owned Lima SSH Unix socket"""

from __future__ import annotations

import os
import socket
import socketserver
import threading
from contextlib import suppress

SOCKET_PATH = os.environ.get("HOME_LAB_AI_SOCKET", "/run/host-ai/llama.sock")
LISTEN_PORT = int(os.environ.get("HOME_LAB_AI_BRIDGE_PORT", "18080"))


def _copy(source: socket.socket, destination: socket.socket) -> None:
    try:
        while data := source.recv(65536):
            destination.sendall(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        with suppress(OSError):
            destination.shutdown(socket.SHUT_WR)


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
            upstream.connect(SOCKET_PATH)
            outbound = threading.Thread(target=_copy, args=(self.request, upstream), daemon=True)
            inbound = threading.Thread(target=_copy, args=(upstream, self.request), daemon=True)
            outbound.start()
            inbound.start()
            outbound.join()
            inbound.join()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", LISTEN_PORT), Handler) as server:
        server.serve_forever()
