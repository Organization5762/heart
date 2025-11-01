import contextlib
import socket
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

DEFAULT_SOCKET_PATH = "/tmp/heart_matrix.sock"
HEADER = struct.Struct("!HHI")


@dataclass
class MatrixClient:
    """Client for pushing RGB frames to the isolated renderer service."""

    socket_path: Optional[str] = None
    tcp_address: Optional[Tuple[str, int]] = None

    def __post_init__(self) -> None:
        if not self.socket_path and not self.tcp_address:
            self.socket_path = DEFAULT_SOCKET_PATH
        if self.socket_path and self.tcp_address:
            raise ValueError("Specify either socket_path or tcp_address, not both")
        self._socket: Optional[socket.socket] = None

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
        frame = image.convert("RGB")
        payload = frame.tobytes()
        header = HEADER.pack(frame.width, frame.height, len(payload))
        sock = self._connect()
        sock.sendall(header)
        sock.sendall(payload)
        self._await_ack(sock)

    def close(self) -> None:
        if self._socket is not None:
            with contextlib.suppress(OSError):
                self._socket.close()
            self._socket = None

    def _await_ack(self, sock: socket.socket) -> None:
        with contextlib.suppress(socket.timeout):
            sock.settimeout(1.0)
            try:
                sock.recv(2)
            finally:
                sock.settimeout(None)


def send_image(
    image: Image.Image,
    *,
    socket_path: Optional[str] = None,
    tcp_address: Optional[Tuple[str, int]] = None,
) -> None:
    client = MatrixClient(socket_path=socket_path, tcp_address=tcp_address)
    try:
        client.send_image(image)
    finally:
        client.close()
