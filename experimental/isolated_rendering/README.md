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
