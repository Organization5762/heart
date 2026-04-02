# Piomatter Row-Window Engine

## Problem

The existing Piomatter parity variants covered different structured rows well, but not with one shared protocol:

- `row-compact`: good general-purpose baseline
- `row-hybrid`: strong for two-span rows such as `quadrants`
- earlier `row-window`: strong for `center-box` style rows

That left the project switching variants by pattern instead of letting one parity-safe encoder adapt per row.

## Design

The row-window protocol is implemented in:

- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_window_engine_parity.pio`
- `/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_window_engine.h`

It now supports four row modes:

- `literal`
- `repeat`
- `split`
- `window`

The encoder now chooses, in order:

- `repeat` when every shifted word matches
- `window` when the row has the shape `edge -> middle -> edge`
- `split` when the row collapses to two repeated spans
- `literal` otherwise

The important detail is that `window` is only used when the fully materialized GPIO row, including OE state, still has the shape:

- `edge -> middle -> edge`

If a row does not match that shape, the encoder falls back to `literal` instead of asserting.

## Parity Guardrail

Parity coverage lives in:

- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs`

Relevant tests:

- `piomatter_row_window_engine_preserves_repeated_and_center_box_rows`
- `piomatter_row_window_engine_preserves_multi_row_frame_waveform`

The multi-row test includes:

- repeated rows
- a center-box row
- a non-window literal row that now exercises the split fallback

That keeps the variant honest across row boundaries and verifies the literal fallback path.

## Local Cost

Local simulated pattern costs from:

- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs`

Current `64x64` row-level results:

- `dark-row`: `row_window 5 words / 141 cycles`
- `repeated-blue`: `row_window 6 words / 149 cycles`
- `alternating`: `row_window 69 words / 146 cycles`
- `quadrants`: `row_window 8 words / 153 cycles`
- `center-box`: `row_window 9 words / 154 cycles`

Compared with `row-compact`:

- `alternating`: `68 words / 149 cycles`
- `quadrants`: `68 words / 149 cycles`
- `center-box`: `68 words / 149 cycles`

So the updated row-window tradeoff is:

- much lower FIFO traffic for `quadrants` and `center-box`
- lower simulated PIO cycles on repeated and alternating rows
- still not a pure cycle win on `center-box`

## Hardware Result

The previously trusted hardware result for the old center-box-only row-window encoder was:

- `center-box`
  - baseline pre: `1066.25 Hz`
  - experiment: `1188.62 Hz`
  - baseline post: `1065.02 Hz`

After broadening the protocol to support `split` rows too, the Pi stopped providing clean benchmark runs. Both the adaptive `row-window` experiment and even a follow-up `row-compact` baseline failed intermittently at:

- `RuntimeError: pio_add_program`

So this pass is simulator-validated and parity-validated, but not yet backed by a new trustworthy grouped Pi number.

## Conclusion

`row-window` is now effectively a row-adaptive structured encoder. Locally it is better than the old center-box-only version because it can also compress true two-span rows such as `quadrants`.

It is still not ready to replace the `best-known` Pi defaults until the remote `pio_add_program` instability is resolved and the grouped hardware benchmarks are reproducible again.
