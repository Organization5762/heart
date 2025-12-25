# Beats streaming IO tuning

## Problem statement

Beats websocket streaming can accumulate outbound frames when clients are slow
or temporarily disconnected. Without bounded queues and overflow control, the
server risks memory growth and added latency for downstream consumers.

## Observations

- `heart.device.beats.websocket.WebSocket` streams frames from the peripheral
  event bus to websocket clients.
- The websocket send loop previously enqueued frames without bounds and waited
  for enqueue completion, which could stall upstream producers.
- Per-client send operations ran sequentially, increasing backpressure when one
  client is slow.

## Configuration additions

The streaming settings are now configurable through environment variables,
exposed via `heart.utilities.env.streaming.StreamingConfiguration` and the
aggregate `heart.utilities.env.Configuration`.

- `HEART_BEATS_STREAM_QUEUE_SIZE`: Maximum number of frames buffered in the
  websocket queue. Use `0` for an unbounded queue.
- `HEART_BEATS_STREAM_OVERFLOW`: Overflow policy when the queue is full.
  Supported values are `drop_newest` and `drop_oldest`.
- `HEART_BEATS_STREAM_JSON_SORT_KEYS`: Toggle JSON key sorting for outbound
  frames.
- `HEART_BEATS_STREAM_JSON_INDENT`: Optional JSON indentation. Set to `none` or
  `null` to disable indentation.

## Behaviour changes

- Frame enqueues are now scheduled without blocking the calling thread.
- Queue overflow handling either drops new frames or drops the oldest buffered
  frame before enqueueing the latest one.
- Frame broadcasts fan out with concurrent sends to reduce IO backpressure
  created by slow websocket clients.

## Materials

- `src/heart/device/beats/websocket.py`
- `src/heart/utilities/env/streaming.py`
- `src/heart/utilities/env/enums.py`
