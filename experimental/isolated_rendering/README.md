# Isolated Rendering Service

This experimental service runs the RGB matrix refresh loop as a dedicated
process. It keeps the most recent frame in memory and continuously pushes it to
the display at a fixed frame rate. Client applications can atomically update
the frame using a lightweight socket protocol without being responsible for the
render cadence themselves.

## Protocol

The service accepts connections over a Unix domain socket (default:
`/tmp/heart_matrix.sock`) or, optionally, TCP. Each frame is sent as a single
message consisting of:

1. A 8-byte header (`>HHI`) containing the frame width, height, and payload size.
1. `width * height * 3` bytes of raw RGB data.

After a frame is processed, the service responds with `OK`.

## Running

```bash
uv run isolated-render run --unix-socket /tmp/heart_matrix.sock --fps 120
```

Pass `--debug` to print frame/update metrics once per second.

### Memory-Mapped Frames (Proof of Concept)

For environments where a third-party renderer wants to share frames without
touching sockets, the service can mirror a memory-mapped file into the live
frame buffer:

```bash
uv run isolated-render run --disable-sockets --mmap-path /tmp/heart_matrix.mmap
```

The renderer process should open the same file and write RGB pixel data using
the helper provided by this package:

```python
from pathlib import Path
from PIL import Image
from isolated_rendering.shared_memory import SharedMemoryFrameWriter

writer = SharedMemoryFrameWriter(Path("/tmp/heart_matrix.mmap"), size=(64, 64))
image = Image.new("RGB", (64, 64), "red")
writer.write_image(image)
```

The writer takes care of the minimal handshake required so that the renderer
never observes a partially written frame.  This mechanism is intentionally
simple—it is a proof of concept that can be swapped out for a more elaborate
protocol in the future.

## Sending Frames

A simple client helper is provided:

```python
from pathlib import Path
from PIL import Image
from isolated_rendering.client import send_image

image = Image.open(Path("frame.png")).convert("RGB")
send_image(image, socket_path="/tmp/heart_matrix.sock")
```

The socket connection stays open across frames, so callers can send multiple
frames without reconnecting by reusing the returned client object.
