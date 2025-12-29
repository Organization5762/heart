# Beats websocket streaming I/O tuning

## Goal

Capture the runtime controls that reduce websocket backpressure when streaming Beats frames. This note documents the queue controls and protobuf payload framing alongside the code paths that consume them.

## Sources

- `src/heart/device/beats/websocket.py`
- `src/heart/device/beats/streaming_config.py`
- `src/heart/runtime/game_loop/__init__.py`

## Materials

- Environment variables (`BEATS_STREAM_QUEUE_SIZE`, `BEATS_STREAM_QUEUE_OVERFLOW`).

## Configuration surface

### Queue sizing

`BEATS_STREAM_QUEUE_SIZE` controls the bounded asyncio queue used by the Beats websocket broadcaster. The queue buffers encoded frames before the broadcast loop fans them out to connected clients. The value must be an integer >= 1; when omitted the queue defaults to 256 entries.

### Queue overflow strategy

`BEATS_STREAM_QUEUE_OVERFLOW` selects the overflow behavior when the broadcast queue is full:

- `drop_oldest` (default): discard the oldest queued frame and enqueue the newest.
- `drop_newest`: discard the incoming frame and retain the queued backlog.
- `error`: raise a `QueueFull` error to surface the overflow condition.

### Protobuf framing

Beats frames and peripheral updates are serialized into protobuf `StreamEnvelope` messages before they are queued for broadcast. This keeps payloads compact and lets the client decode binary frames without JSON parsing on every update.

## Runtime behavior summary

- Frames are enqueued using non-blocking operations from the websocket send path, so the renderer thread does not stall when the queue is saturated.
- Broadcast fan-out happens concurrently per client, reducing head-of-line blocking when one connection is slow.
- Overflow behavior is determined by the strategy selection, so operators can prefer freshness (`drop_oldest`) or completeness (`drop_newest`) depending on the audience.
- Websocket shutdown requests stop the broadcast worker, close the server, and join the background thread so keyboard interrupts unwind without leaving a live event loop.
