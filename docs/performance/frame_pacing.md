# Render Loop Frame Pacing

## Technical problem

The main loop currently renders as fast as the renderer workload allows, then relies
on `clock.tick(self.max_fps)` to cap the upper bound. On high-cost renderer stacks,
that behavior can keep the CPU pegged even when additional frames do not provide
meaningful visual gains on slower devices.

## Change summary

- The loop now consults recent renderer timing samples to compute an adaptive
  minimum frame interval when `HEART_RENDER_FRAME_PACING_STRATEGY=adaptive`.
- `HEART_RENDER_FRAME_MIN_INTERVAL_MS` provides a fixed lower bound for pacing,
  and `HEART_RENDER_FRAME_UTILIZATION_TARGET` tunes how much headroom to leave
  above the estimated render cost.

## Materials

None.
