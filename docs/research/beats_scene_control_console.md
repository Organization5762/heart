# Beats Scene Control Console Research Note

## Summary

Add a DAW-style control surface to the Beats Electron stream view so operators can tune scene parameters, bind sensor-driven reactions, and mock sensor values from the same screen.

## Motivation

The previous stream page was a passive viewer with only websocket status and FPS readouts. That made it hard to shape the Three.js scene, inspect sensor values, or rehearse telemetry-driven behavior without editing code or attaching real hardware.

## Implementation Notes

- The stream route now presents a transport-style header, a scene mixer, a responsive plugin rack, and a dedicated sensor console on the same page.
- Scene controls are modeled in `experimental/beats/src/features/stream-console/scene-config.ts` and applied live in `experimental/beats/src/components/stream-cube.tsx`.
- Sensor extraction, override evaluation, and history sampling live under `experimental/beats/src/features/stream-console/` so the UI reads one consistent model for live and mocked channels.
- The plugin rack and sensor console are implemented in `experimental/beats/src/components/scene-plugin-dock.tsx`, `experimental/beats/src/components/sensor-lab-panel.tsx`, and `experimental/beats/src/components/sensor-history-chart.tsx`.
- Focused unit coverage for the sensor simulation utilities lives in `experimental/beats/src/tests/unit/features/stream-console/sensor-simulation.test.ts`.

## Source References

- `experimental/beats/src/components/stream.tsx`
- `experimental/beats/src/components/stream-cube.tsx`
- `experimental/beats/src/components/scene-plugin-dock.tsx`
- `experimental/beats/src/components/sensor-lab-panel.tsx`
- `experimental/beats/src/components/sensor-history-chart.tsx`
- `experimental/beats/src/features/stream-console/scene-config.ts`
- `experimental/beats/src/features/stream-console/sensor-simulation.ts`
- `experimental/beats/src/features/stream-console/use-sensor-simulation.ts`

## Materials

- Node.js and npm for the Electron/Vite workspace under `experimental/beats`
