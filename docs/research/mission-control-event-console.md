# Mission Control Event Console Research Note

## Summary

Add an ambient event console, scenario deck, and phase runbook to the Electron mission control route so the UI suggests a control-room environment without recreating specific mission-control operations.

## Motivation

The existing mission control view provides a timeline, system status, and telemetry snapshot but lacks a thematic event feed and phase runbook to reinforce the control-room atmosphere. Adding those elements supports full-mission rehearsal while keeping the experience intentionally stylized.

## Implementation Notes

- The event console renders the most recent ambient mission events and the next milestone marker from a static schedule.
- The scenario deck provides pre-configured simulation variants and keeps the selection in local state.
- The phase runbook maps each mission phase to operator cues, shown in a dedicated card on the right column.

## Source References

- `experimental/beats/src/routes/mission-control/index.tsx`

## Materials

- None.
