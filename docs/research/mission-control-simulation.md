# Mission Control Simulation Console Research Note

## Summary

Add a mission-control-style operations console to the Electron renderer so operators can rehearse an end-to-end Apollo-like mission timeline while monitoring simulated subsystem status and telemetry checkpoints.

## Motivation

The current Electron UI provides peripheral, stream, and device views but lacks a unified control-room experience. Introducing a mission timeline and simulation controls makes the application feel like a historical flight director station while offering an in-app rehearsal loop.

## Proposed Experience

- Present a mission timeline that advances through discrete phases (pre-launch through recovery).
- Provide a mission elapsed time clock and a phase callout panel to simulate flight director voice loops.
- Offer start, pause, reset, and rate controls to rehearse the full mission quickly.
- Display a Go/No-Go poll panel with subsystem statuses and quick telemetry snapshot cards.

## Implementation Notes

- The UI is implemented as a new route under `experimental/beats/src/routes/mission-control/index.tsx`.
- Navigation is added to the main sidebar in `experimental/beats/src/components/app-sidebar.tsx`.
- The simulation loop uses a simple interval timer with a selectable rate to update elapsed time and phase state.

## Source References

- `experimental/beats/src/routes/mission-control/index.tsx`
- `experimental/beats/src/components/app-sidebar.tsx`

## Materials

- None.
