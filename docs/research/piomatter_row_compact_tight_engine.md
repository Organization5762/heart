# Piomatter Row Compact Tight Engine

## Goal

Try a smaller-cycle sibling of the existing compact protocol without changing the compact command stream or its render override.

## Design

Source files:

- `rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_engine_parity.pio`
- `rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_tight_engine_parity.pio`
- `docs/research/generated/piomatter_override/render_row_compact_engine.h`

The `row-compact-tight` variant keeps the same command words as `row-compact`:

- literal rows still encode `width` plus inline `active_hold_count`
- repeated rows still encode one repeated GPIO word plus the same trailer words

The tight variant keeps the same compact commands and the same GPIO word ordering, but it reduces the fixed trailer timing:

- the inactive-hold word drops the extra delay bit
- the next-address word drops one delay cycle
- short trailers also emit the active-hold word without the extra delay

That changes dwell timing, but not the shifted GPIO words or their transition ordering.

## Validation Surface

Relevant tests and benchmarks:

- `rust/heart_rgb_matrix_driver/src/runtime/tests.rs`
- `rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs`
- `scripts/benchmark_piomatter_row_repeat.py`

The intended validation is:

- compare `row-compact-tight` against `row-compact` in simulation
- require identical shifted low/high GPIO words and identical GPIO transition ordering
- require fewer simulated PIO cycles
- then run grouped Pi benchmarks: baseline pre, experiment, baseline post
