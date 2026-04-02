# Piomatter Row-Runs Engine

## Problem

`row-compact` is a good general-purpose parity path, but it still treats structured rows like `quadrants` and `center-box` as dense literal payloads. Those rows are not dense in any meaningful sense: they are just a few repeated spans with long runs.

## Materials

- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_runs_engine_parity.pio](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_runs_engine_parity.pio)
- [/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_runs_engine.h](/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/render_row_runs_engine.h)
- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs)
- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs)

## Change

The row-runs parity engine is a specialized PIO path for rows that collapse to at most four repeated spans. The command word carries:

- additional run count after the first span
- first run width
- inline active-hold count

Payload words then provide:

- first repeated GPIO word
- for each extra run: count word + repeated GPIO word
- the same active/inactive/next-address trailer words as the other Piomatter parity engines

This keeps the same externally visible row waveform as the Piomatter row-repeat baseline while cutting both FIFO bytes and PIO loop work for structured rows.

## Expected Effect

- solid fills use one repeated run
- quadrant rows use two repeated runs
- center-box rows use three or four runs depending on the active/inactive cutoff
- dense alternating rows are intentionally unsupported and should stay on `row-compact`

## Validation

- `./.venv/bin/python rust/heart_rgb_matrix_driver/tools/generate_pi5_pio_programs.py`
- `cargo test --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --lib piomatter_row_runs_engine_preserves_repeated_quadrant_and_center_box_rows -- --nocapture`
- `cargo run --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --bin piomatter_row_pattern_cost -- --pattern structured`
- `cargo check --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --all-targets`
- `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make format`
- `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
