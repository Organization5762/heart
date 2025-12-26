# Render Loop Frame Pacing Research Notes

## Why pacing belongs in the main loop

The render loop currently renders every iteration and only applies a hard cap at
`clock.tick(self.max_fps)`. The loop itself makes no allowance for render cost
estimates, so even expensive renderer stacks can drive the loop continuously when
`max_fps` is high.

## Quoted sources

- `src/heart/runtime/game_loop.py` (main loop structure):

  > "renderers = self.\_select_renderers()"
  > "self.\_one_loop(renderers)"
  > "clock.tick(self.max_fps)"

- `src/heart/runtime/rendering/timing.py` (render timing aggregation):

  > "def estimate_total_ms(self, renderers: Iterable[\_RendererLike]) -> tuple\[float, bool\]:"
  > "total_ms += state.average_ms"

These locations show that the loop already has access to renderer timing data
and applies a single FPS cap, which supports adding pacing logic that references
those timing estimates.
