import contextlib
import os
import socketserver
import struct
import threading
from typing import Optional, Tuple

from heart.device.isolated_render import HEADER
from heart.utilities.logging import get_logger

from .buffer import FrameBuffer

logger = get_logger(__name__)


class _ThreadedServer(socketserver.ThreadingMixIn):
    daemon_threads = True
    allow_reuse_address = True


class UnixFrameServer(_ThreadedServer, socketserver.UnixStreamServer):
    def __init__(self, socket_path: str, frame_buffer: FrameBuffer):
        self.socket_path = socket_path
        if os.path.exists(socket_path):
            os.remove(socket_path)
        super().__init__(socket_path, FrameUpdateHandler)
        self.frame_buffer = frame_buffer

    def cleanup(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.socket_path)


class TCPFrameServer(_ThreadedServer, socketserver.TCPServer):
    def __init__(self, address: Tuple[str, int], frame_buffer: FrameBuffer):
        super().__init__(address, FrameUpdateHandler)
        self.frame_buffer = frame_buffer


class FrameUpdateHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = getattr(self.request, "getpeername", lambda: "unix")()
        logger.debug("Client connected: %s", peer)
        try:
            while True:
                header = self.rfile.read(HEADER.size)
                if not header:
                    break
                try:
                    width, height, payload_len = HEADER.unpack(header)
                except struct.error:
                    logger.warning("Received malformed header from %s", peer)
                    break

                payload = self._read_exact(payload_len)
                if payload is None:
                    logger.warning("Incomplete payload from %s", peer)
                    break

                try:
                    self.server.frame_buffer.update_raw(width, height, payload)
                except ValueError as exc:
                    logger.warning("Rejected frame from %s: %s", peer, exc)
                    break

                with contextlib.suppress(BrokenPipeError):
                    self.wfile.write(b"OK")
                    self.wfile.flush()
        finally:
            logger.debug("Client disconnected: %s", peer)

    def _read_exact(self, length: int) -> Optional[bytes]:
        remaining = length
        chunks: list[bytes] = []
        while remaining:
            chunk = self.rfile.read(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


@contextlib.contextmanager
def serve_in_background(server: socketserver.BaseServer):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        cleanup = getattr(server, "cleanup", None)
        if callable(cleanup):
            cleanup()
