# Peripherals and Beats

## Problem Statement

Document how peripherals, display geometry, and beats integrations are wired so deployments can
match hardware expectations without digging through runtime internals.

## Peripheral Manager Overview

`heart.peripheral.core.manager.PeripheralManager` supervises peripheral discovery and starts
worker threads for each device family, including:

- Bluetooth switches and controllers (`heart.peripheral.switch`, `heart.peripheral.gamepad`).
- Serial devices (`heart.peripheral.uart`).
- Heart-rate monitoring (`heart.peripheral.heart_rates`).

Devices publish events into the shared `EventBus` and can be combined with virtual peripherals
for higher-level gestures.

## Display Geometry

Display layout is defined through environment variables:

- `HEART_DEVICE_LAYOUT`: `cube` or `rectangle`.
- `HEART_LAYOUT_COLUMNS` / `HEART_LAYOUT_ROWS`: panel grid dimensions for rectangular layouts.
- `HEART_PANEL_COLUMNS` / `HEART_PANEL_ROWS`: per-panel pixel dimensions (default `64×64`).

Use `heart.device.layout` to confirm the runtime interpretation of these values.

## Beats Integrations

Beats-related components currently include:

- The cube renderer that maps beats to per-face visuals.
- Snapshot tooling for capturing peripheral states.
- WebSocket + protobuf schemas for streaming beats data across processes.

Reference implementations live under `heart.renderers.beats_*` and
`heart.peripheral.beats_*` (use `rg "beats" src/heart` to locate the latest modules).

## Related References

- `docs/library/tooling_and_configuration.md` for `totem_debug` peripherals commands.
- `docs/library/runtime_systems.md` for event flow and feedback loops.
