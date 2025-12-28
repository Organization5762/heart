# Render loop pacing notes

## Problem statement

We need a pacing approach that can slow the main loop when renderers are already
consuming most of the available frame budget. The goal is to throttle rendering
based on recent timing estimates without blocking faster frames when the system
has spare capacity.

## Materials

- `src/heart/runtime/rendering/timing.py`
- `src/heart/runtime/render/planner.py`
- `src/heart/runtime/game_loop/core.py`
- `docs/library/runtime_systems.md`

## Source excerpts

- "`self.average_ms = (ema_alpha * duration_ms) + ((1.0 - ema_alpha) * self.average_ms)`" (`src/heart/runtime/rendering/timing.py`)
- "`estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(`" (`src/heart/runtime/render/planner.py`)
- "`clock.tick(self.max_fps)`" (`src/heart/runtime/game_loop/core.py`)

## Notes

The timing tracker already smooths renderer durations with EMA, which gives a
useful signal for estimating current render cost. The planner already treats
timing snapshots as an input for deciding work distribution. The loop still
ticks on a maximum FPS guardrail, so pacing can be layered in without removing
the existing clock cap.

## Design takeaways

- Use the timing tracker estimates to compute a target interval that keeps
  renderer utilization below a configurable threshold.
- Preserve the existing FPS cap so operators can still bound frame rates
  regardless of render cost.
- Make pacing opt-in so workloads can decide when throttling is appropriate.
