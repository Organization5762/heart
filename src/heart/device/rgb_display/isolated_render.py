import contextlib
import socket
import struct
import zlib
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

from heart.device.rgb_display.constants import DEFAULT_SOCKET_PATH
from heart.utilities.env.enums import (IsolatedRendererAckStrategy,
                                       IsolatedRendererDedupStrategy)
from heart.utilities.logging import get_logger

HEADER = struct.Struct("!HHI")


logger = get_logger(__name__)


@dataclass
class MatrixClient:
    """Client for pushing RGB frames to the isolated renderer service."""

    socket_path: Optional[str] = None
    tcp_address: Optional[Tuple[str, int]] = None
    ack_strategy: IsolatedRendererAckStrategy = IsolatedRendererAckStrategy.ALWAYS
    ack_timeout_seconds: float = 1.0
    dedup_strategy: IsolatedRendererDedupStrategy = (
        IsolatedRendererDedupStrategy.SOURCE
    )

    def __post_init__(self) -> None:
        if not self.socket_path and not self.tcp_address:
            self.socket_path = DEFAULT_SOCKET_PATH
        if self.socket_path and self.tcp_address:
            raise ValueError("Specify either socket_path or tcp_address, not both")
        self._socket: Optional[socket.socket] = None
        self._last_payload_signature: Optional[tuple[int, int, int]] = None
        self._last_source_signature: Optional[tuple[str, int, int, int]] = None

    def _connect(self) -> socket.socket:
        if self._socket is not None:
            return self._socket
        if self.socket_path:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
        else:
            assert self.tcp_address is not None
            sock = socket.create_connection(self.tcp_address)
        self._socket = sock
        return sock

    def send_image(self, image: Image.Image) -> None:
        if self.dedup_strategy is IsolatedRendererDedupStrategy.SOURCE:
            if self._should_skip_source(image):
                logger.debug(
                    "Skipping isolated renderer payload (dedup strategy: %s)",
                    self.dedup_strategy.value,
                )
                return
            frame, payload, payload_signature = self._prepare_payload(image)
        elif self.dedup_strategy is IsolatedRendererDedupStrategy.PAYLOAD:
            frame, payload, payload_signature = self._prepare_payload(image)
            if payload_signature == self._last_payload_signature:
                logger.debug(
                    "Skipping isolated renderer payload (dedup strategy: %s)",
                    self.dedup_strategy.value,
                )
                return
        else:
            frame, payload, payload_signature = self._prepare_payload(image)
        header = HEADER.pack(frame.width, frame.height, len(payload))
        sock = self._connect()
        sock.sendall(header)
        sock.sendall(payload)
        self._last_payload_signature = payload_signature
        if self.dedup_strategy is IsolatedRendererDedupStrategy.SOURCE:
            self._last_source_signature = self._source_signature(image)
        if self.ack_strategy is IsolatedRendererAckStrategy.ALWAYS:
            self._await_ack(sock)

    def close(self) -> None:
        if self._socket is not None:
            with contextlib.suppress(OSError):
                self._socket.close()
            self._socket = None

    def _await_ack(self, sock: socket.socket) -> None:
        if self.ack_timeout_seconds <= 0:
            return
        with contextlib.suppress(socket.timeout):
            sock.settimeout(self.ack_timeout_seconds)
            try:
                sock.recv(2)
            finally:
                sock.settimeout(None)

    def _prepare_payload(
        self, image: Image.Image
    ) -> tuple[Image.Image, bytes, tuple[int, int, int]]:
        if image.mode == "RGB":
            frame = image
        else:
            frame = image.convert("RGB")
        payload = frame.tobytes()
        signature = (frame.width, frame.height, zlib.adler32(payload))
        return frame, payload, signature

    def _should_skip_source(self, image: Image.Image) -> bool:
        signature = self._source_signature(image)
        return signature == self._last_source_signature

    def _source_signature(self, image: Image.Image) -> tuple[str, int, int, int]:
        payload = image.tobytes()
        return (image.mode, image.width, image.height, zlib.adler32(payload))
