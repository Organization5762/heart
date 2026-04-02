# Piomatter Row-Compact Inline Active-Hold Compression

## Problem

The previous Piomatter row-repeat parity path preserved the GPIO waveform, but every row still paid for a host-driven trailer:

- active hold count
- active hold word
- inactive hold word
- next-address word

That cost extra FIFO words and extra PIO instructions even when the shift payload itself was already optimal.

## Materials

- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_engine_parity.pio](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_engine_parity.pio)
- [/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_compact_engine.h](/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_compact_engine.h)
- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs)
- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs)

## Change

The row-compact parity program keeps the Piomatter row payload model but moves the fixed inactive/latch/address trailer timing into the PIO program. The current compact command word now carries:

- row kind (`literal` or `repeat`)
- inline active-hold count
- row width

That removes the separate active-hold count payload word entirely. The short-trailer case still uses an implicit `out pins, 32 [1]` dwell when the inline count is zero, while counted trailers reuse the inline count and jump into the same active-hold loop. The visible GPIO sequence stays aligned with the Piomatter row-repeat baseline because only the command packing changed.

## Expected Effect

- fully uniform rows still collapse to a single repeated row command
- dense nonuniform rows keep their literal GPIO payload but no longer spend a separate FIFO word on active-hold count
- short active-hold rows still use the implicit one-cycle trailer path
- repeated and dense rows both reduce simulated PIO instruction count compared with the row-repeat baseline while preserving the Piomatter parity trace used by the local simulator tests

## Validation

- `./.venv/bin/python rust/heart_rgb_matrix_driver/tools/generate_pi5_pio_programs.py`
- `cargo test --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --lib piomatter_row_compact_engine_preserves_repeated_nonuniform_quadrant_and_center_box_rows -- --nocapture`
- `cargo test --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --lib piomatter_row_compact_engine_preserves_dark_rows_with_a_shorter_trailer -- --nocapture`
- `cargo run --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --bin piomatter_row_pattern_cost -- --pattern all`
- `cargo check --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --all-targets`
- `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make format`
- `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
