# Piomatter Row-Hybrid Engine

## Goal

Add a parity-checked Piomatter experiment that chooses the cheapest safe row encoding per row:

- `repeat` for fully uniform rows
- `split` for rows that collapse into exactly two repeated spans
- `literal` for everything else

This keeps the general case correct while letting structured scenes like quadrant layouts use a much smaller FIFO payload.

## Source Files

- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_hybrid_engine_parity.pio`
- `/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_hybrid_engine.h`
- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs`
- `/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs`
- `/Users/lampe/.codex/worktrees/b4c5/heart/scripts/benchmark_piomatter_row_repeat.py`

## Command Shape

The command word uses the top two bits for row mode:

- `00`: literal row
- `01`: repeated row
- `10`: two-span split row

The lower fields still carry:

- inline active-hold count
- inline first row width / first split width

All rows share the same compact trailer:

- active hold GPIO word
- inactive hold GPIO word
- next-address hold GPIO word

## Parity

The local parity guard now checks a multi-row frame, not just individual rows.

The hybrid engine is compared against the existing Piomatter row-repeat baseline across one frame that mixes:

- a repeated row
- a dense literal row
- a two-span split row

The test asserts:

- identical low GPIO words
- identical clock-high GPIO words
- identical externally visible pin transitions

This is stricter than the earlier row-only checks and is meant to prevent protocols that look right for one row but drift across row boundaries.

## Local Cost

On the local row-pattern cost benchmark:

- `quadrants`: `72 -> 7` words, `153 -> 154` cycles
- `alternating`: `72 -> 68` words, `153 -> 149` cycles
- `center-box`: `72 -> 68` words, `153 -> 149` cycles
- `repeated-blue`: `9 -> 5` words, `155 -> 151` cycles

Interpretation:

- the hybrid protocol keeps the compact literal path for dense rows
- it only pays extra decode work when it can collapse a row into a true split form
- for `quadrants`, it behaves like the more aggressive split protocol without forcing the whole frame into a split-only contract

## Hardware Result

Grouped benchmark on `totem1` for:

- `256x64`
- `5 planes`
- `0 temporal`
- `100 MHz`
- `MAX_XFER=262140`
- `pattern=quadrants`

Measured:

- `row-compact`: `289.91 Hz` baseline pre
- `row-hybrid`: `466.50 Hz`
- `row-compact`: `286.34 Hz` baseline post

That result stayed below the shift-only plausibility ceiling, so it is treated as a real improvement rather than a broken transfer-cadence artifact.

## Caveat

The Pi-side row-hybrid startup is still flaky on some follow-up runs and can fail at `pio_add_program`. The trustworthy result so far is the grouped `quadrants` benchmark above. Solid-fill and other general-case grouped benchmarks should be treated as unresolved until that Pi-side instability is cleaned up.
