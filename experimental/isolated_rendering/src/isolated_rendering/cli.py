import signal
import socketserver
from typing import Optional

import typer

from .buffer import FrameBuffer
from .renderer import RenderLoop, create_device
from .server import TCPFrameServer, UnixFrameServer, serve_in_background

app = typer.Typer(help="Dedicated renderer service for the heart matrix output")


def _create_server(
    frame_buffer: FrameBuffer,
    unix_socket: Optional[str],
    tcp_host: str,
    tcp_port: int,
) -> socketserver.BaseServer:
    if unix_socket:
        return UnixFrameServer(unix_socket, frame_buffer)
    if tcp_port:
        return TCPFrameServer((tcp_host, tcp_port), frame_buffer)
    raise typer.BadParameter("Provide either --unix-socket or --tcp-port")


@app.command()
def run(
    unix_socket: Optional[str] = typer.Option(
        "/tmp/heart_matrix.sock",
        help="Path to the unix domain socket to listen on",
    ),
    tcp_host: str = typer.Option("127.0.0.1", help="Host to bind when using TCP"),
    tcp_port: int = typer.Option(0, help="Port to bind when using TCP"),
    fps: float = typer.Option(120.0, help="Target frames per second for refresh"),
    debug: bool = typer.Option(False, help="Print debug metrics once per second"),
    x11_forward: bool = typer.Option(
        False,
        help="Force use of X11 forwarding / LocalScreen output even on Pi",
    ),
) -> None:
    device = create_device(x11_forward=x11_forward)
    frame_buffer = FrameBuffer(size=device.full_display_size())
    server = _create_server(frame_buffer, unix_socket, tcp_host, tcp_port)
    render_loop = RenderLoop(
        device=device, frame_buffer=frame_buffer, fps=fps, debug=debug
    )

    def _signal_handler(signum, frame):
        render_loop.stop()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    with serve_in_background(server):
        try:
            render_loop.run_forever()
        except KeyboardInterrupt:
            render_loop.stop()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
