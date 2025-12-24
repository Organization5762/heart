# Renderer Event Bus Bridge

## Summary

Renderer pipelines can now emit and consume intermediate frames through the shared event bus. `RendererEventPublisher` wraps any `BaseRenderer` and converts its output surface into a `RendererFrame` payload (`src/heart/renderers/internal/event_stream.py`). Downstream consumers register with `RendererEventSubscriber` or the updated `RenderImage` to subscribe to those frames, avoiding direct surface hand-offs.

## Motivation

Composed renderers previously passed `pygame.Surface` objects through method parameters or mutable state. That coupling made it difficult to fan out intermediate results to multiple consumers and prevented reuse across game modes. Publishing frames on the event bus promotes loose coupling: any renderer can observe shared channels, respect producer IDs, and rebuild the surface locally.

## Event Flow

1. A publisher renders into its provided surface and immediately encodes the pixels into a `RendererFrame` event. The payload carries the logical channel, renderer name, frame sequence, and raw bytes. (`RendererEventPublisher.from_surface()`)
1. The event bus records the payload in the `StateStore` and synchronously invokes subscribers. (`src/heart/peripheral/core/event_bus.py`)
1. Subscribers filter by channel (and optional producer ID), rebuild a `pygame.Surface`, scale it to the active window, and blit the result. (`RendererEventSubscriber._handle_frame()`)
1. `RenderImage` now delegates to the subscriber path when `subscribe_channel` is provided, caching the rendered surface in its atomic state for reuse by transitions or testing. (`src/heart/renderers/image.py`)

## Observations and Follow-up

- `RendererFrame` lives alongside other event payloads and serializes bytes without assuming the final display size. Consumers scale as needed, so upstream publishers can target their native resolution. (`src/heart/peripheral/input_payloads.py`)
- Tests cover the integration path from publisher to subscriber to guarantee surfaces round-trip through the bus. (`tests/display/test_renderer_event_stream.py`)
- Future work: expose richer metadata contracts (e.g., color space, depth) and add throttling controls so high-frequency publishers do not starve the event bus.
