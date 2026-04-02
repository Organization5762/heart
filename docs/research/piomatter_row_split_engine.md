# Piomatter Row-Split Engine

## Goal

Add a parity-checked Piomatter experiment that compresses rows made of one repeated word or two repeated spans.

This targets scenes like:

- solid fills
- left/right half splits
- row-local active/inactive cutoffs for a repeated color

The implementation lives in:

- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_split_engine_parity.pio`
- `/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_split_engine.h`
- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs`

## Command Shape

The row-split engine accepts:

- repeated row commands
- two-span split row commands
- the same short/counting trailer distinction used by the compact row engine

It does not accept dense literal rows. That is intentional: it is a targeted experiment for rows that collapse into one or two runs.

## Parity

Local parity checks compare the row-split engine against the existing Piomatter row-repeat baseline and assert:

- identical shifted low GPIO words
- identical shifted clock-high GPIO words
- identical externally visible pin transition sequences

The checked cases are:

- repeated rows
- repeated rows with an in-row `OE` cutoff
- two-span quadrant rows

## What Worked

The row-split engine is valid for:

- full repeated rows
- rows that split cleanly into two repeated spans

That includes the important repeated-color + `OE` cutoff case, which makes the experiment relevant to solid-fill scenes even when the active portion of the row does not span the full width.

## What Did Not Work

On the `quadrants` full-frame hardware benchmark, some row-plane passes did not collapse to two spans because the row payload still embeds `OE` state per shifted pixel. In those passes, the row can become three or four runs instead of two, so the render override cannot encode the frame safely as a pure row-split stream.

This means:

- row-split is not a general replacement for row-compact
- row-split is best treated as a targeted experiment for scenes whose row payloads truly stay within one or two runs

## Measurement Caveat

Piomatter's `matrix.fps` measures the transfer/replay loop cadence, not guaranteed completed panel refresh.

For extremely small transfer blobs, `matrix.fps` can exceed the shift-only ceiling implied by:

- PIO target frequency
- panel width
- row count
- plane count

That is a sign the benchmark is overcounting submission cadence rather than true visible refresh. The benchmark script now emits a shift-only ceiling and marks such runs as implausible.
