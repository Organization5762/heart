# Heart Repository Agent Instructions

## Installing

Use the tooling in this repository to manage environments. Prefer `uv` for Python dependency resolution.

- On Pi 5, install the `heart_pi5_scan_loop` kernel module through DKMS via `packages/heart-device-manager` instead of ad-hoc `insmod` so kernel updates rebuild it automatically.
- Pin prerelease Python dependencies with exact versions in `pyproject.toml` so `uv.lock` resolves the intended alpha or beta release.
- Scene and asset bootstrap can run before `pygame.display.set_mode`; avoid unconditional `convert()` or `convert_alpha()` calls in asset constructors and defer display-dependent conversion until a surface exists.
- `DisplayContext` wraps the active `pygame.Surface`; renderers that need surface-only APIs such as `subsurface()` must use `window.screen` after confirming it is initialized instead of calling those APIs on `DisplayContext` directly.
- Only the real display-owned `DisplayContext` may change pygame display modes; scratch or post-processing contexts must keep `can_configure_display=False` and never call `pygame.display.set_mode()`.
- OpenGL-backed renderers must treat `reset()` as lifecycle teardown: cascade reset into nested runtimes and restore mutated UI state such as mouse visibility so mode switches can leave GPU-backed scenes cleanly.
- Pi 5 resident-scan backends own steady-state refresh in hardware; the generic Rust runtime worker should wait for new work instead of re-submitting an unchanged active frame in software.
- When benchmarking Pi-side Rust binaries remotely, prefer `cargo run --manifest-path ...` over direct `target/release/...` invocations; stale per-crate binaries can linger under `rust/heart_rust/target` and silently skew measurements.

## Formatting

Run `make format` before committing changes. This applies Ruff fixes, isort, Black, docformatter, and mdformat to Python sources and documentation. Documentation updates should avoid marketing language, state the technical problem in plain terms, and include a materials list when relevant.

- If `make format` fails in the sandbox because `uv` cannot write under `~/.local/share/uv/tools`, run the equivalent `.venv/bin/isort`, `.venv/bin/ruff check --fix`, and `cargo fmt` commands for the touched files and record both the failure and the fallback commands in Recent Validation.

- Avoid declaring module-level `__all__` exports. Prefer explicit imports at call sites instead of curating export lists.

- Define device identifiers (such as firmware `device_name` values) as module-level constants instead of inline literals.

- Avoid building filesystem paths via string concatenation. Use `os.path.join` or `pathlib.Path` instead.

- Prefer `pathlib.Path` over `os.path.join` when constructing paths, and ensure functions annotated to return a `Path` return a `Path` object.

- Keep standalone distributable packages under `packages/<distribution-name>/src/<import_name>` and wire them into the root project with local `tool.uv.sources` path dependencies.

- When CLI arguments accept file paths, parse them as `pathlib.Path` objects and ensure parent directories exist before writing.

- Avoid using `print` for runtime diagnostics in CLI commands; use the shared logger.

- Avoid using `print` for runtime diagnostics in peripheral modules; use the shared logger.

- Avoid leaving commented debug print statements in production modules; remove them once they are no longer needed.

- Avoid wildcard imports; use explicit imports so dependencies stay clear and tooling can track usage.

- Prefer f-strings over string concatenation when assembling Python strings so formatting stays readable.

- Prefer mixins or composition over direct inheritance.

- Prefer direct code over single-use wrapper layers; when a helper only forwards to one caller, inline it or delete it.

- Prefer `StrEnum` values over raw strings for strategy/configuration mode selections.

- Use `heart.utilities.logging.get_logger` for internal logging so handlers and log levels stay consistent across modules.

- Prefer `get_logger(__name__)` so loggers include their module path and stay consistent in telemetry.

- When starting background threads, provide a descriptive name via `threading.Thread(name=...)` to keep diagnostics readable.

- Prefer module-level constants for tunable loop intervals instead of embedding sleep literals in long-running loops.

- Prefer module-level constants for retry thresholds in reconnect or recovery loops instead of inline numeric literals.

- Use `time.monotonic()` for elapsed-time comparisons, and reserve `time.time()` for wall-clock timestamps that leave the process.

- Prefer `pathlib.Path.read_text`/`write_text` helpers for straightforward text file I/O.

- When reading or writing text files, specify an explicit encoding (prefer `utf-8`) to keep behavior consistent across platforms.

- Use module-level constants for public constructor or function default values so shared configuration is easy to discover and adjust.

- When parsing PATH-like environment variables, strip whitespace from each entry and ignore empty values before converting to `Path` objects.

- Use module-level constants for default argument values and shared string literals in firmware helpers so configuration stays consistent.

- Keep mixed PyO3 packages in a `rust/<package>/` layout with the Rust crate in `src/`, Python shims in `python/<package>/`, and a private native submodule exposed via `tool.maturin.module-name` to avoid import ambiguity.

- Keep PyO3 `extension-module` support behind a crate feature that Maturin enables for extension builds so `cargo test` and `cargo bench` can link without Python-extension linker behavior.

- After changing exported PyO3 classes or Python shims under `rust/<package>/python/`, rerun `uv sync --extra native` before Python validation so the active virtualenv rebuilds the local extension with the matching symbols.

- PyO3 stub-generation binaries require a linkable Python 3.11 runtime in addition to Rust; if `cargo run --bin stub_gen` fails with unresolved `Py*` symbols, install or point PyO3 at a Python 3.11 build before retrying.
- Rust runtime tuning knobs should live in `rust/heart_rust/src/runtime/tuning.rs` and use `HEART_*` environment variables instead of file-local magic constants.

- Guard Raspberry Pi `pinctrl` integration tests behind `HEART_RUN_PI5_PINCTRL_TESTS=1` and mark them with `pytest.mark.integration` so normal desktop test runs stay hardware-free.

- Pi 5 DMA/PIO benchmark work depends on `libpio-dev` being installed on the target host so the native transport shim can compile and link against `libpio`.

- For the Pi 5 HUB75 path on the Adafruit bonnet pin map, scan-format compaction mainly reduces per-group control words; each shifted column still needs a full sparse pin-state word unless the output strategy is redesigned around different pin grouping.

- The Pi 5 resident scan-buffer loop is the correct way to skip unchanged frames: keep replaying the active packed frame until a new one arrives instead of leaving the panel idle between updates.

- Keep Rust unit tests hardware-agnostic under `cfg(test)` even on Raspberry Pi hosts; validate real Pi 5 scanout and transport behavior through the Pi-only Python tests and benchmark targets instead of unit-test backend auto-detection.

## Dependency Injection (Lagom)

- Prefer using `heart.runtime.container.build_runtime_container` and the provider registration helpers in
  `heart.peripheral.core.providers` rather than instantiating new Lagom `Container` objects in feature modules.
- Only `heart.runtime.container` and `heart.peripheral.core.providers` should import Lagom types directly. Other
  modules should depend on `heart.runtime.container.RuntimeContainer` when they need to reference the container
  type so dependency wiring stays centralized.
- Feature modules should register singleton bindings with provider helpers (for example,
  `register_singleton_provider`) instead of reaching for Lagom bindings directly, so container usage remains
  encapsulated.
- When tracking runtime containers for provider registration updates, use weak references (for example,
  `weakref.WeakSet`) so stale containers do not stay alive after shutdown.
- Define Lagom provider factories as named module-level callables instead of inline lambdas so the dependency
  graph stays discoverable and traceable in logs and stack traces.

## Error Handling

- Avoid catching `BaseException`; catch `Exception` or more specific error types so system-exiting signals propagate.
- Avoid raising bare `Exception` values; raise more specific exception types instead.
- Avoid swallowing recoverable exceptions; log them with the shared logger (use debug-level logging for high-frequency loops).
- When logging caught exceptions at error level, include traceback context with `logger.exception` (or `exc_info=True`) unless you intentionally suppress it.
- Avoid placeholder early returns or unreachable docstrings in production methods; remove stubs once real implementations are available.
- For CLI commands, log expected user-facing errors and exit with `typer.Exit` instead of raising generic exceptions.

## Testing

Run `make test` to execute the Pytest suite located in the `tests/` directory. Ensure all tests pass before submitting changes.

When adding tests, it is reasonable to stub hardware- or framework-heavy dependencies so the core logic can be exercised in isolation.

- Parameterize new Pytest cases when validating multiple input permutations (especially for driver behaviour) to keep coverage
  clear and maintainable.
- Write tests with precise assertions and include a short docstring at the top of every test function that explains the behaviour
  being validated. Each test docstring must mention both the specific behaviour under test and why that behaviour matters at a
  higher level (e.g., performance, resilience, integration, documentation value). Group related tests into descriptive `pytest`
  classes and give every class a docstring that states the shared focus and broader value of the grouped scenarios so readers can
  immediately understand the collection's intent.

## Linting (Optional Pre-Check)

Running `make check` is recommended to verify formatting and linting without applying fixes.

## Documentation Guidelines

Update `docs/code_flow.md` and re-render the diagram with `scripts/render_code_flow.py` whenever runtime architecture changes. Pair thoughtful implementations with a research note under `docs/research/` that cites the relevant source files. Plans under `docs/planning/` must follow the structure defined in their `AGENTS.md` file, and contributors should review the master project list in `docs/planning/README.md` before scoping new work. Before implementing a proposal, check `docs/planning/` for related higher-level plans and review any relevant documents.

## File Focus

Keep files narrowly scoped. If a module starts handling multiple concerns (e.g., orchestration plus parsing plus rendering), split the responsibilities into smaller, purpose-built modules so each file does slightly fewer things and has a clear single focus.
- When a Pi 5 scanout experiment stops being the supported path, delete the retired module params, probe binaries, and alternate replay branches instead of leaving dormant tuning code behind.

## Environment Cleanup

If a single file or module starts accumulating setup, orchestration, configuration, and cleanup logic, move those responsibilities into smaller, focused modules or helpers so each file handles fewer concerns and is easier to reason about.

## Configuration Defaults

Define CLI default values as module-level constants so they stay consistent across commands and are easy to review.

## Validation

- `make format`
- `make test`

## Recent Validation

- `2026-03-31`: `make format`, `cargo check --manifest-path rust/heart_rust/Cargo.toml`, and `make test` after making Pi 5 scan format codec helpers explicitly `pub(crate)`.
- `2026-03-31`: `make format`, `cargo check --manifest-path rust/heart_rust/Cargo.toml`, and `make test` after adding maintainer-level comments across `rust/heart_rust/src/runtime/pi5_scan.rs`.
- `2026-03-31`: `make format`, `cargo check --manifest-path rust/heart_rust/Cargo.toml`, and `make test` after splitting `write_scan_segment()` into small private helpers without changing the packed Pi 5 scan format.
- `2026-03-31`: `make format`, `cargo check --manifest-path rust/heart_rust/Cargo.toml`, and `make test` after deleting dead Pi 5 scan helper constructors/wrappers.
- `2026-03-31`: `cargo check --manifest-path rust/heart_rust/Cargo.toml`
- `2026-03-31`: `make format`
- `2026-03-31`: `make test`
- `2026-03-31`: `pytest -n0 tests/device/test_heart_rust_rgbmatrix_compat.py`
- `2026-03-31`: `make format`
- `2026-03-31`: `make test`
- `2026-03-31`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`
- `2026-03-31`: `make format`
- `2026-03-31`: `make test`
- `2026-03-31`: `cargo check --manifest-path rust/heart_rust/Cargo.toml`
- `2026-03-31`: `make format`
- `2026-03-31`: `make test`
- `2026-03-30`: `cargo check` in `rust/heart_rust`
- `2026-03-30`: `make format`
- `2026-03-30`: `make test`
- `2026-03-30`: `cargo run --bin stub_gen` in `rust/heart_rust` failed at link time because this environment still lacks a linkable Python 3.11 runtime for PyO3 stub generation.
- `2026-03-30`: `uv lock`
- `2026-03-30`: `.venv/bin/isort src tests`, `.venv/bin/ruff check --fix src tests`, `.venv/bin/docformatter -i -r --config ./pyproject.toml docs`, and `.venv/bin/mdformat docs` after `make format` hit a sandboxed uv cache permission error.
- `2026-03-30`: `.venv/bin/pytest` after `make test` hit the same sandboxed uv cache permission error.
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/yolisten/renderer.py tests/renderers/test_yolisten_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/yolisten/renderer.py tests/renderers/test_yolisten_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_yolisten_renderer.py`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/text/renderer.py tests/renderers/test_text_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/text/renderer.py tests/renderers/test_text_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_text_renderer.py`
- `2026-03-30`: `.venv/bin/isort src/heart/runtime/rendering/renderer_processor.py src/heart/runtime/rendering/timing.py tests/runtime/test_renderer_processor.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/runtime/rendering/renderer_processor.py src/heart/runtime/rendering/timing.py tests/runtime/test_renderer_processor.py`
- `2026-03-30`: `.venv/bin/pytest tests/runtime/test_renderer_processor.py`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/spritesheet_random/renderer.py src/heart/programs/configurations/lib_2025.py tests/renderers/test_spritesheet_random_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/spritesheet_random/renderer.py src/heart/programs/configurations/lib_2025.py tests/renderers/test_spritesheet_random_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_spritesheet_random_renderer.py`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/isort src/heart/navigation/game_modes.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/navigation/game_modes.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/pytest tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py` after preserving `FractalScene`'s OPENGL mode and nested runtime reinitialization.
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-31`: `cargo test --manifest-path rust/heart_rust/Cargo.toml`
- `2026-03-31`: `make format`
- `2026-03-31`: `make test`
- `2026-03-31`: `make format` and `make test` after rewriting `rust/heart_rust/README.md`.
- `2026-03-31`: `make format` and `make test` after simplifying the Pi 5 `/dev/pio0` availability check in `rust/heart_rust/src/runtime/backend.rs`.
- `2026-03-31`: `make format` and `make test` after centralizing Rust runtime tuning knobs in `rust/heart_rust/src/runtime/tuning.rs` and making the PyO3 boundary parse `WiringProfile` / `ColorOrder` before calling `MatrixDriverCore::new`.
- `2026-03-30`: Remote on `michael@totem1.local`: `make install-pi5-scan-loop-module`, `PIO_BENCH_CHAIN_LENGTH=4 PIO_BENCH_ITERATIONS=3 PIO_BENCH_FRAME_COUNT=16 make bench-matrix-pio-scan`, and `HEART_RUN_PI5_SCAN_TESTS=1 .venv/bin/pytest -n0 tests/device/test_rgb_display_pi5_scan_benchmark.py`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 11 --iterations 3 --frame-count 16 --resident-loop-ms 100 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: `.venv/bin/isort src/heart/utilities/env/rendering.py src/heart/runtime/rendering/renderer_processor.py tests/runtime/test_renderer_processor.py tests/utilities/test_env.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/utilities/env/rendering.py src/heart/runtime/rendering/renderer_processor.py tests/runtime/test_renderer_processor.py tests/utilities/test_env.py`
- `2026-03-30`: `.venv/bin/pytest tests/runtime/test_renderer_processor.py`
- `2026-03-30`: `.venv/bin/pytest tests/utilities/test_env.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py` after removing fractal runtime display-context reconfiguration.
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/navigation/composed_renderer.py src/heart/navigation/game_modes.py tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/navigation/composed_renderer.py src/heart/navigation/game_modes.py tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/pytest tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/three_fractal/provider.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/three_fractal/provider.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/three_fractal/renderer.py tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_three_fractal_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/hilbert_curve/provider.py src/heart/renderers/hilbert_curve/renderer.py tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/hilbert_curve/provider.py src/heart/renderers/hilbert_curve/renderer.py tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/runtime/display_context.py src/heart/runtime/game_loop/__init__.py src/heart/navigation/game_modes.py tests/runtime/test_display_context.py tests/runtime/test_game_loop.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/runtime/display_context.py src/heart/runtime/game_loop/__init__.py src/heart/navigation/game_modes.py tests/runtime/test_display_context.py tests/runtime/test_game_loop.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/pytest tests/runtime/test_display_context.py tests/runtime/test_game_loop.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make format` failed because `uv` could not write under `/Users/lampe/.local/share/uv/tools/.tmp1CLZAq` in this sandbox.
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/renderers/hilbert_curve/provider.py tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/renderers/hilbert_curve/provider.py tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `.venv/bin/pytest tests/renderers/test_hilbert_curve_renderer.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/code/heart/.uv-cache make test`
- `2026-03-31`: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`
- `2026-03-31`: `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`
- `2026-03-31`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`
- `2026-03-31`: `.venv/bin/isort rust/heart_rust/python/heart_rust/matrix.py rust/heart_rust/python/heart_rust/__init__.py src/heart/device/rgb_display/runtime.py tests/device/test_heart_rust_matrix_api.py`
- `2026-03-31`: `.venv/bin/ruff check --fix rust/heart_rust/python/heart_rust/matrix.py rust/heart_rust/python/heart_rust/__init__.py src/heart/device/rgb_display/runtime.py tests/device/test_heart_rust_matrix_api.py`
- `2026-03-31`: `.venv/bin/pytest -n0 tests/device/test_heart_rust_matrix_api.py tests/device/test_rgb_display_runtime.py`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/b4c5/heart/.uv-cache .venv/bin/mdformat docs/research/pi5_scan_transport_layers.md`
- `2026-03-31`: `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`
- `2026-03-31`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`
- `2026-03-31`: Remote Pi kernel rebuild with `ssh michael@totem1.local 'cd /home/michael/heart/rust/heart_rust/kernel/pi5_scan_loop && make -j4'` after the C-file documentation pass.
- `2026-03-31`: Remote Pi Rust check with `ssh michael@totem1.local 'cd /home/michael/heart/rust/heart_rust && ~/.cargo/bin/cargo check --bin pi5_scan_bench'` after the C-file documentation pass.
- `2026-03-31`: `bash -n packages/heart-device-manager/src/heart_device_manager/install_rgb_matrix.sh packages/heart-device-manager/src/heart_device_manager/install_pi5_scan_loop_dkms.sh`
- `2026-03-31`: `uv build ./rust/heart_rust --wheel --out-dir /tmp/heart-rust-dist -v` confirmed the maturin backend used `profile` from `rust/heart_rust/pyproject.toml` and finished a `release` build.
- `2026-03-31`: Remote Pi kernel rebuild with `ssh michael@totem1.local 'cd /home/michael/heart/rust/heart_rust/kernel/pi5_scan_loop && make -j4'`
- `2026-03-31`: Remote Pi dense benchmark with `ssh michael@totem1.local 'cd /home/michael/heart && ~/.cargo/bin/cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 11 --iterations 1 --frame-count 8 --resident-loop-ms 200 --frame-pattern dense'` after reloading `heart_pi5_scan_loop.ko batch_target_bytes=2097152`
- `2026-03-30`: `cargo fmt` in `rust/heart_rust`
- `2026-03-30`: `.venv/bin/isort src/heart/device/rgb_display/device.py src/heart/device/rgb_display/runtime.py tests/device/test_rgb_display_runtime.py rust/heart_rust/python/heart_rust/__init__.py rust/heart_rust/python/heart_rust/matrix.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/device/rgb_display/device.py src/heart/device/rgb_display/runtime.py tests/device/test_rgb_display_runtime.py rust/heart_rust/python/heart_rust/__init__.py rust/heart_rust/python/heart_rust/matrix.py`
- `2026-03-30`: `.venv/bin/mdformat AGENTS.md`
- `2026-03-30`: `cargo check` in `rust/heart_rust`
- `2026-03-30`: `python -m pytest tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/b4c5/heart/.uv-cache make format` failed because `uv` still attempted to write under `/Users/lampe/.local/share/uv/tools/.tmpwbJ6BV` in this sandbox.
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/b4c5/heart/.uv-cache make test`
- `2026-03-30`: `cargo fmt` in `rust/heart_rust` after splitting `lib.rs` into a thin PyO3 API and `src/runtime.rs`
- `2026-03-30`: `cargo check` in `rust/heart_rust`
- `2026-03-30`: `python -m pytest tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `cargo fmt` in `rust/heart_rust` after adding detached PyO3 matrix calls, Rayon-backed color remapping, unit tests, and the `matrix_transfer` benchmark.
- `2026-03-30`: `cargo fmt` in `rust/heart_rust` after adding the Pi 5 scan scheduler, FIFO-fed scan shim, and `pi5_scan_bench`.
- `2026-03-30`: `cargo check --tests --benches` in `rust/heart_rust`
- `2026-03-30`: `cargo test` in `rust/heart_rust`
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: remote Pi 5 `cargo test` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: remote Pi 5 `cargo bench --bench matrix_transfer -- --quick` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: remote Pi 5 `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=1 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5 PIO_BENCH_FRAME_COUNT=64 PIO_BENCH_PIPELINE_DEPTH=2`
- `2026-03-30`: remote Pi 5 `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=4 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5 PIO_BENCH_FRAME_COUNT=64 PIO_BENCH_PIPELINE_DEPTH=2`
- `2026-03-30`: remote Pi 5 `make bench-matrix-pio-scan PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=1 PIO_BENCH_PARALLEL=1 PIO_BENCH_ITERATIONS=1 PIO_BENCH_FRAME_COUNT=1 PIO_BENCH_PIPELINE_DEPTH=1`
- `2026-03-30`: remote Pi 5 `make bench-matrix-pio-scan PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=4 PIO_BENCH_PARALLEL=1 PIO_BENCH_ITERATIONS=1 PIO_BENCH_FRAME_COUNT=1 PIO_BENCH_PIPELINE_DEPTH=1`
- `2026-03-30`: remote Pi 5 `make test-matrix-pio-scan`
- `2026-03-30`: remote Pi 5 `.venv/bin/python -m pytest -n0 tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo test` in `rust/heart_rust` failed at link time because this environment still lacks a linkable Python 3.11 runtime for PyO3 test binaries.
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo bench --bench matrix_transfer -- --quick` in `rust/heart_rust` failed at link time for the same missing Python 3.11 runtime.
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo check --tests --benches` in `rust/heart_rust`
- `2026-03-30`: `python -m pytest tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo test` in `rust/heart_rust` after gating PyO3 `extension-module` behind the `python-extension` feature and enabling it only through Maturin.
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo bench --bench matrix_transfer -- --quick` in `rust/heart_rust` after the same PyO3 packaging fix.
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo run --bin stub_gen` in `rust/heart_rust`
- `2026-03-30`: `python -m pytest tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `cargo fmt` in `rust/heart_rust` after splitting the clean-room matrix runtime into `runtime/` submodules, adding frame-buffer pooling, and expanding the benchmark surface.
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo check --tests --benches` in `rust/heart_rust`
- `2026-03-30`: `.venv/bin/isort src/heart/device/rgb_display/runtime.py tests/device/test_rgb_display_runtime.py tests/device/test_rgb_display_transfer_benchmark.py scripts/render_code_flow.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/device/rgb_display/runtime.py tests/device/test_rgb_display_runtime.py tests/device/test_rgb_display_transfer_benchmark.py scripts/render_code_flow.py`
- `2026-03-30`: `.venv/bin/mdformat docs/code_flow.md docs/research/hub75_clean_room_runtime_prd.md`
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `python -m py_compile /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/scripts/remote_hub75_check.py`
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo test` in `rust/heart_rust`
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo bench --bench matrix_transfer -- --quick` in `rust/heart_rust`
- `2026-03-30`: `CARGO_HOME=/Users/lampe/.codex/worktrees/b4c5/heart/.cargo-home cargo run --bin stub_gen` in `rust/heart_rust`
- `2026-03-30`: `python -m pytest -n0 tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/b4c5/heart/.uv-cache uv sync --extra native`
- `2026-03-30`: `python -m pytest -n0 tests/device/test_rgb_display_transfer_benchmark.py --benchmark-min-rounds=3 --benchmark-max-time=0.02`
- `2026-03-30`: `.venv/bin/isort src/heart/device/rgb_display/debug.py tests/device/test_rgb_display_pinctrl_debug.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/device/rgb_display/debug.py tests/device/test_rgb_display_pinctrl_debug.py`
- `2026-03-30`: `python -m pytest -n0 tests/device/test_rgb_display_pinctrl_debug.py` (skipped on the local macOS host because `HEART_RUN_PI5_PINCTRL_TESTS` was unset and `pinctrl` is Pi-specific)
- `2026-03-30`: `python -m py_compile /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/scripts/remote_hub75_check.py`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bootstrap-native`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo test` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo bench --bench matrix_transfer -- --quick` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --bin stub_gen` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: Remote on `michael@totem1.local`: `make debug-matrix-pinctrl`
- `2026-03-30`: Remote on `michael@totem1.local`: `make test-matrix-pinctrl`
- `2026-03-30`: Remote on `michael@totem1.local`: `HEART_RUN_PI5_PINCTRL_TESTS=1 .venv/bin/python -m pytest -n0 tests/device/test_rgb_display_runtime.py tests/device/test_rgb_display_pinctrl_debug.py tests/device/test_rgb_display_transfer_benchmark.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `cargo fmt` in `rust/heart_rust` after adding the Pi 5 DMA/PIO transport probe, `libpio` C shim, transport benchmark binary, and Pi-only integration coverage.
- `2026-03-30`: `cargo check --tests --benches` in `rust/heart_rust`
- `2026-03-30`: `cargo test` in `rust/heart_rust`
- `2026-03-30`: `cargo bench --bench matrix_transfer -- --quick` in `rust/heart_rust`
- `2026-03-30`: `cargo run --bin pi5_pio_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 11 --iterations 1` in `rust/heart_rust` failed as expected on the local macOS host because the Pi 5 DMA/PIO transport is only supported on Linux aarch64.
- `2026-03-30`: `python -m pytest -n0 tests/device/test_rgb_display_pi5_dma_benchmark.py tests/device/test_rgb_display_pinctrl_debug.py tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `.venv/bin/mdformat docs/code_flow.md docs/research/hub75_clean_room_runtime_prd.md AGENTS.md /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/SKILL.md`
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `python -m py_compile /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/scripts/remote_hub75_check.py`
- `2026-03-30`: `bash -n scripts/bootstrap_native_runtime.sh`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bootstrap-native`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo test` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo bench --bench matrix_transfer -- --quick` in `/home/michael/heart/rust/heart_rust`, including the new `pi5_pack_transport_rgba` and `pi5_dma_transport` groups
- `2026-03-30`: Remote on `michael@totem1.local`: `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=1 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=4 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --bin stub_gen` in `/home/michael/heart/rust/heart_rust`
- `2026-03-30`: Remote on `michael@totem1.local`: `make debug-matrix-pinctrl`
- `2026-03-30`: Remote on `michael@totem1.local`: `make test-matrix-pinctrl`
- `2026-03-30`: Remote on `michael@totem1.local`: `make test-matrix-pio-dma`
- `2026-03-30`: Remote on `michael@totem1.local`: `HEART_RUN_PI5_PINCTRL_TESTS=1 HEART_RUN_PI5_PIO_TESTS=1 .venv/bin/python -m pytest -n0 tests/device/test_rgb_display_runtime.py tests/device/test_rgb_display_pinctrl_debug.py tests/device/test_rgb_display_pi5_dma_benchmark.py tests/device/test_rgb_display_transfer_benchmark.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `cargo fmt` and `cargo check` in `rust/heart_rust` after adding the pipelined full-cycle Pi 5 DMA/PIO benchmark path.
- `2026-03-30`: `python -m pytest -n0 tests/device/test_rgb_display_pi5_dma_benchmark.py` on the local macOS host (skipped because `HEART_RUN_PI5_PIO_TESTS` was unset and the benchmark is Pi-specific).
- `2026-03-30`: `python -m py_compile /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/scripts/remote_hub75_check.py`
- `2026-03-30`: `.venv/bin/mdformat /Users/lampe/code/settings/codex/skills/rpi5-hub75-bringup/SKILL.md AGENTS.md`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=1 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5 PIO_BENCH_FRAME_COUNT=64 PIO_BENCH_PIPELINE_DEPTH=2`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bench-matrix-pio-dma PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=4 PIO_BENCH_PARALLEL=1 PIO_BENCH_PWM_BITS=11 PIO_BENCH_ITERATIONS=5 PIO_BENCH_FRAME_COUNT=64 PIO_BENCH_PIPELINE_DEPTH=2`
- `2026-03-30`: `cargo check --tests --benches`, `cargo test`, and `cargo bench --bench matrix_transfer -- --quick` in `rust/heart_rust` after moving the Rust benchmark sources into `rust/heart_rust/bench/` and wiring Cargo paths explicitly.
- `2026-03-30`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_dma_probe --bin pi5_scan_bench`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release -p heart_rust --bin pi5_scan_dma_probe -- --max-transfer-words 1`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release -p heart_rust --bin pi5_scan_dma_probe -- --max-transfer-words 16`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release -p heart_rust --bin pi5_scan_dma_probe -- --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `make bench-matrix-pio-scan PIO_BENCH_PANEL_ROWS=64 PIO_BENCH_PANEL_COLS=64 PIO_BENCH_CHAIN_LENGTH=1 PIO_BENCH_PARALLEL=1 PIO_BENCH_ITERATIONS=1 PIO_BENCH_FRAME_COUNT=1 PIO_BENCH_PIPELINE_DEPTH=1`
- `2026-03-30`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_gpio_probe`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release -p heart_rust --bin pi5_gpio_probe -- --gpio 17 --cycles 3 --sleep-ms 50`
- `2026-03-30`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe`
- `2026-03-30`: Remote on `michael@totem1.local`: `strace -o /tmp/piolib_simple_xfer.strace -f -e trace=openat,ioctl /tmp/piolib_simple_xfer`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program simple --pattern delay --word-count 2 --max-transfer-words 16`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program scan --pattern delay --word-count 2 --max-transfer-words 16`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program simple --pattern delay --word-count 5720 --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program scan --pattern delay --word-count 5720 --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program scan --pattern data --word-count 5720 --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program scan --pattern alternating --word-count 5720 --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_pio_ioctl_probe -- --program scan --pattern segment --word-count 5720 --max-transfer-words 5720`
- `2026-03-30`: Remote on `michael@totem1.local`: `strace -o /tmp/pi5_scan_bench.strace -f -e trace=ioctl cargo run --release --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 1 --frame-count 1 --pipeline-depth 1`
- `2026-03-30`: Remote on `michael@totem1.local`: `cargo run --release --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 1 --frame-count 1 --pipeline-depth 1` is currently blocked by repeated `rustc` SIGSEGV crashes during dependency rebuild on the Pi.
- `2026-03-30`: `cargo fmt` and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_pio_bench --bin pi5_scan_bench` after deleting the temporary Pi probe/debug binaries and removing their probe-only runtime hooks.
- `2026-03-30`: `cargo fmt`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench --bin pi5_pio_bench` after tuning the Pi 5 scan packer and DMA submission loop.
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 5 --frame-count 32 --pipeline-depth 2`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --iterations 5 --frame-count 32 --pipeline-depth 2`
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, and `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba` after exposing Pi 5 scan dwell and clock-divider benchmark knobs plus derived scan-schedule metrics.
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 2 --frame-count 8 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 2 --frame-count 8 --pipeline-depth 2 --lsb-dwell-ticks 1 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --iterations 2 --frame-count 8 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 3 --frame-count 16 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.5`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 3 --frame-count 16 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.25`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 3 --frame-count 16 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 2 --frame-count 8 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 0.95`, `0.9`, `0.85`, and `0.8` to probe the lower scan-clock stability boundary; values below `1.0` either failed DMA buffer configuration (`errno=19`) or timed out during submission (`errno=110`).
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench --benches`, and `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba` after deleting the obsolete transport-only Pi DMA benchmark path (`pi5_pio_bench`, `pi5_dma`, and related tests/targets).
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, and `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba` after splitting Pi 5 scan transport submission and drain into an async queue-backed transport worker while preserving the synchronous benchmark path.
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 2 --frame-count 8 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `.venv/bin/python -m pytest -n0 tests/device/test_rgb_display_runtime.py tests/navigation/test_native_scene_manager.py`
- `2026-03-30`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench` after updating the pipelined scan benchmark path to use `submit_async()` and `wait_complete()` instead of synchronous `stream()`.
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench` after exposing `pwm_bits` as a scan-benchmark knob.
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 8 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `CARGO_BUILD_JOBS=1 RUST_MIN_STACK=16777216 cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 8 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, and `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba` after compacting the Pi 5 scan-group format so the PIO program owns latch, blanking, and dwell sequencing with five control words per row-pair / bitplane group.
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `.venv/bin/pytest tests/device/test_rgb_display_pi5_scan_benchmark.py` (skipped on the local macOS host because `HEART_RUN_PI5_SCAN_TESTS` was unset)
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/.cargo/bin/cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 11 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/.cargo/bin/cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 11 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/heart/rust/heart_rust/target/release/pi5_scan_bench --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 11 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/heart/rust/heart_rust/target/release/pi5_scan_bench --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 11 --iterations 5 --frame-count 32 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0`
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, and `.venv/bin/pytest tests/device/test_rgb_display_pi5_scan_benchmark.py` after adding explicit `display_hz` and `submit_hz` fields to the Pi 5 scan benchmark output (the pytest case remained skipped locally because `HEART_RUN_PI5_SCAN_TESTS` was unset).
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/.cargo/bin/cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 11 --iterations 3 --frame-count 16 --pipeline-depth 2 --lsb-dwell-ticks 2 --clock-divider 1.0` to confirm the new `display_hz` versus `submit_hz` reporting on real Pi hardware.
- `2026-03-30`: `cargo fmt`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, `.venv/bin/pytest tests/device/test_rgb_display_pi5_scan_benchmark.py`, `python scripts/render_code_flow.py --output docs/code_flow.svg`, and `.venv/bin/mdformat AGENTS.md docs/code_flow.md docs/research/hub75_clean_room_runtime_prd.md` after switching the Pi 5 transport worker to resident scan-buffer looping and reducing the benchmark to stable `display_hz` plus resident-loop metrics.
- `2026-03-30`: Remote on `michael@totem1.local`: `/home/michael/.cargo/bin/cargo run --release --manifest-path /home/michael/heart/rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- --panel-rows 64 --panel-cols 64 --chain-length 4 --parallel 1 --pwm-bits 11 --iterations 3 --frame-count 16 --pipeline-depth 2 --resident-loop-ms 100 --lsb-dwell-ticks 2 --clock-divider 1.0` measured resident-loop first-render latency and steady-state refresh on real Pi hardware.
- `2026-03-30`: Remote on `michael@totem1.local`: rebuilt `heart_pi5_scan_loop.ko` after adding an experimental direct cyclic-DMA replay path; benchmarked `pi5_scan_bench` for `chain_length=1` and `chain_length=4` with `cyclic_dma=0` and `cyclic_dma=1`. Result: `cyclic_dma=1` slightly raised `x1` steady replay (`~489.7 Hz` vs `~479.7 Hz`) but did not improve `x4` steady replay (`~129.9 Hz`) and reduced one-shot `display_hz`, so the module default remains `cyclic_dma=0`.
- `2026-03-31`: Added `rust/heart_rust/bench/rp1_mmio_bench.c` and, on `michael@totem1.local`, compiled it with `gcc -O3 -std=c11 -Wall -Wextra`. Remote `/dev/mem` writes into RP1 shared SRAM measured about `345.3 MB/s` across `4 KiB`, `16 KiB`, `64 KiB`, and `128 KiB` regions, confirming the earlier `~48 MB/s` ceiling is specific to the PIO/DMA replay path rather than the host-to-RP1 link in general.
- `2026-03-31`: Remote on `michael@totem1.local`: rebuilt `heart_pi5_scan_loop.ko` with an experimental `sink_program` mode that drains the PIO TX FIFO without HUB75 scan logic. Benchmarks showed the same steady replay ceiling as the full scan path (`~46.6 MB/s` for `chain_length=1`, `~47.7 MB/s` for `chain_length=4`), confirming the limiter is the PIO TX replay path itself rather than the scan program.
- `2026-03-31`: Remote on `michael@totem1.local`: swept experimental `dma_maxburst` values on the direct cyclic-DMA sink path. `dma_maxburst=1`/`2` collapsed throughput to `~7.3 MB/s`, `4` reached `~29.4 MB/s`, and `8` or higher plateaued at the same `~47.7 MB/s` ceiling, so larger bursts do not break through the existing limit.
- `2026-03-31`: Remote on `michael@totem1.local`: restored the default `heart_pi5_scan_loop.ko` settings after the sink/burst experiments and re-ran `pi5_scan_bench` for `64x64`, `chain_length=4`, `parallel=1`, `pwm_bits=11`, confirming the standard resident-loop path remained at `~129.9 Hz` steady refresh.
- `2026-03-31`: Added `rust/heart_rust/bench/pi5_scan_multi_session_bench.c` and, on `michael@totem1.local`, compiled it with `gcc -O3 -std=c11 -Wall -Wextra`. In `sink_program=1` mode, aggregate replay throughput scaled past the single-channel ceiling: `1` session `~46.6 MB/s`, `2` sessions `~93.2 MB/s`, `3` sessions `~118-125 MB/s`, and `4` sessions `~141-143 MB/s`, showing the `~48 MB/s` limit is per TX channel rather than global to RP1.
- `2026-03-31`: Added `rust/heart_rust/bench/rp1_pio_fifo_mmio_bench.c` and, on `michael@totem1.local`, compiled it with `gcc -O3 -std=c11 -Wall -Wextra`. Direct MMIO writes to the RP1 PIO TX FIFO in `sink_program=1` mode measured `~159.7 MB/s`, proving the DMA replay path, not the FIFO itself, was the single-channel bottleneck.
- `2026-03-31`: Remote on `michael@totem1.local`: rebuilt `heart_pi5_scan_loop.ko` with an experimental `mmio_replay=1` path that writes packed frames directly into the PIO TX FIFO from the kernel worker. `pi5_scan_bench` then measured `~156.3 MB/s` / `~1609 Hz` steady replay for `chain_length=1` and `~157.9 MB/s` / `~429.7 Hz` steady replay for `chain_length=4`, for both `sink_program=1` and the real scan program.
- `2026-03-31`: Remote on `michael@totem1.local`: compared `mmio_replay` using scalar `writel_relaxed()` versus `iowrite32_rep()` (`mmio_rep=1`). The repeated-write helper did not improve throughput (`~157.9 MB/s` either way for `chain_length=4`) and worsened one-shot `display_hz`, so the benchmark module now defaults to `mmio_replay=1` with the scalar MMIO loop.
- `2026-03-31`: Remote on `michael@totem1.local`: compared normal device MMIO versus `ioremap_wc()` (`mmio_wc=1`) for the PIO TX FIFO in the `mmio_replay` path. Write-combining nearly doubled single-session throughput: `chain_length=1` rose from `~156.3 MB/s` to `~325.3 MB/s`, and `chain_length=4` rose from `~157.9 MB/s` / `~429.7 Hz` to `~334.2 MB/s` / `~909.4 Hz`. The kernel loop module now defaults to `mmio_wc=1`.
- `2026-03-31`: Remote on `michael@totem1.local`: multi-session sink benchmarks with `mmio_replay=1` and `mmio_wc=1` scaled aggregate replay throughput well beyond the old DMA ceiling: about `325 MB/s` for `1` session, `609-635 MB/s` for `2`, `818-845 MB/s` for `3`, and `983 MB/s` to `1.03 GB/s` for `4`, confirming the old `~48 MB/s` ceiling was a replay-path artifact rather than a hard RP1 link limit.
- `2026-03-31`: Remote on `michael@totem1.local`: rebuilt `heart_pi5_scan_loop.ko` after adding `mmio_raw` and `mmio_unroll8` replay modes. With `mmio_wc=1`, unrolling the MMIO FIFO stores raised single-session sink throughput from `~336 MB/s` to `~555-556 MB/s` and raised real `64x64 x4`, `parallel=1`, `pwm_bits=11` resident refresh from `~915 Hz` to `~1514-1515 Hz`; raw stores were not materially better than unrolled `writel_relaxed()`, so the module now defaults to `mmio_unroll8=1` with `mmio_raw=0`.
- `2026-03-31`: Remote on `michael@totem1.local`: multi-session sink benchmarks with `mmio_replay=1`, `mmio_wc=1`, and `mmio_unroll8=1` reached about `556 MB/s` for `1` session, `1.07 GB/s` for `2`, `1.43 GB/s` for `3`, and `1.71 GB/s` for `4`, confirming the unrolled WC replay path scales well beyond the earlier per-channel ceiling.
- `2026-03-31`: Remote on `michael@totem1.local`: tested `mmio_cached_frame=1` to keep MMIO replay frames in cached kernel memory. Under `mmio_wc=1` this produced implausibly high apparent refresh (`>5 GB/s` sink throughput), and neither `wmb()`, `pio_sm_tx_fifo_level()`, nor experimental FIFO-alias readback (`mmio_fifo_read_flush=1`) made the completion accounting trustworthy. The working conclusion is that WC-mapped posted writes are not ordered with the current drain/count path, so `mmio_wc=1` is left experimental and the honest module default is back to non-WC MMIO replay (`mmio_wc=0`, `mmio_cached_frame=0`).
- `2026-03-31`: Remote on `michael@totem1.local`: revalidated the honest non-WC MMIO replay path after the WC flush experiments. `64x64 x4`, `parallel=1`, `pwm_bits=11` measured about `157.99 MB/s` sink throughput and about `429.9 Hz` steady resident refresh, matching the direct non-WC FIFO MMIO measurements and confirming the earlier `~546-556 MB/s` WC numbers were measurement artifacts rather than true device-paced refresh.
- `2026-03-31`: Remote on `michael@totem1.local`: swept non-WC MMIO write primitives (`scalar`, `writel_relaxed` unroll-8, `__raw_writel`, `__raw_writel` unroll-8, and `iowrite32_rep`). All converged to the same honest single-session sink throughput (`~157-158 MB/s`), which confirms the non-WC ceiling is the RP1 FIFO/device path rather than CPU loop overhead.
- `2026-03-31`: Remote on `michael@totem1.local`: size-swept the sink benchmark from `4 KiB` to `4 MiB` frames for both non-WC and WC coherent MMIO replay. Non-WC plateaued at `~157 MB/s`, while WC coherent climbed with frame size and stabilized at `~559 MB/s` for `1 MiB` and `4 MiB` frames. The WC coherent path also sustained `~1485 Hz` on real `64x64 x4`, `parallel=1`, `pwm_bits=11` scan over a `1 s` window. That makes `mmio_wc=1` with `mmio_cached_frame=0` the best supported default again; the invalid configuration is specifically cached-source WC replay.
- `2026-03-31`: Remote on `michael@totem1.local`: added a `mmio_writesl` replay mode and compared it with `iowrite32_rep()` and the unrolled `writel_relaxed()` WC coherent path. `writesl()` and `iowrite32_rep()` both dropped single-session sink throughput to `~330 MB/s`, while the unrolled `writel_relaxed()` path held `~545 MB/s`, so the unrolled relaxed-store path remains the best FIFO writer.
- `2026-03-31`: Remote on `michael@totem1.local`: rechecked multi-session sink throughput with the final WC coherent default (`mmio_wc=1`, `mmio_cached_frame=0`, `mmio_unroll8=1`). Aggregate throughput reached about `544.5 MB/s` for `1` session, `1.06 GB/s` for `2`, `1.41 GB/s` for `3`, and `1.70 GB/s` for `4`, confirming the higher single-session result scales cleanly.
- `2026-03-31`: Remote on `michael@totem1.local`: added `mmio_unroll16` and `mmio_prefetch` replay modes and compared them with the WC coherent `mmio_unroll8` default. The larger unroll and source prefetch did not materially change single-session sink throughput (`~546-547 MB/s`) or steady `64x64 x4` resident refresh (`~1486-1490 Hz`), so `mmio_unroll8=1` remains the default.
- `2026-03-31`: Remote on `michael@totem1.local`: tried the arm64 `__iowrite32_copy()` helper as a FIFO writer. That path hung `pi5_scan_bench` badly enough to require a Pi reboot, so the experimental `mmio_copy32` path was removed rather than left available as a footgun.
- `2026-03-31`: Remote on `michael@totem1.local`: after rebooting from the failed `mmio_copy32` experiment, a one-off run briefly reported about `661-670 MB/s` sink throughput and `~1821 Hz` steady `64x64 x4` refresh, but that spike did not survive a clean rebuild/reload of the module. The reproducible post-cleanup baseline returned to about `547 MB/s` single-session sink throughput and `~1490 Hz` steady `64x64 x4` resident refresh for the WC coherent `mmio_unroll8` path.
- `2026-03-31`: Remote on `michael@totem1.local`: exposed `clkdiv_mul` / `clkdiv_div`, `worker_cpu`, and `worker_fifo_low` as kernel module parameters. Sweeping the PIO clock divider from `2.0` down to `0.25` did not materially change sink throughput or steady `64x64 x4` replay on the WC coherent path, and pinning the replay worker to CPU 0 with `sched_set_fifo_low()` likewise left the steady ceiling unchanged at about `546-547 MB/s` / `~1490 Hz`. Those paths remain available for debugging, but they are not meaningful tuning levers for the current bottleneck.
- `2026-03-31`: Remote on `michael@totem1.local`: added `mmio_batch_replays` so the MMIO worker can replay the same resident frame multiple times before a single drain/completion sync, while still keeping the very first presentation unbatched. On `64x64 x4`, `parallel=1`, `pwm_bits=11`, `mmio_batch_replays=8` or higher improved steady resident refresh from about `1488 Hz` to about `1536 Hz` and raised single-session sink throughput from about `546.8 MB/s` to about `564.4 MB/s`. The gain is modest (`~3%`), but it confirms the drain/completion path still costs some throughput on unchanged-frame replay.
- `2026-03-31`: Remote on `michael@totem1.local`: `mmio_batch_replays` does not materially improve beyond `16`; `4` and `8` reached about `1528 Hz` / `561.5 MB/s`, while `16` and `32` plateaued at about `1536 Hz` / `564.4 MB/s`. The first-presentation latency stayed flat at about `0.73 ms`, but one-shot `display_hz` becomes intentionally less meaningful because later waits can complete in batched chunks rather than one presentation at a time.
- `2026-03-31`: Added all-black group compression to the Pi 5 scan format. Packed scan groups now emit a compact blank-run opcode when every shifted pixel word equals the group `blank_word`, and the kernel-loop / userspace PIO programs gained a matching blank-run branch. Local validation: `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench` and `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`.
- `2026-03-31`: Remote on `michael@totem1.local`: with the blank-run format and `mmio_batch_replays=8`, `64x64 x4`, `parallel=1`, `pwm_bits=11` now scales with actual packed bytes instead of always paying the dense worst case. Dense synthetic frames shrank from `91,872` words to `67,392` words (`96` blank groups compressed) and steady resident refresh rose from about `1,536 Hz` to about `2,088 Hz`. Fully black frames shrank to `2,112` words (`352` blank groups compressed) and reached about `55.5 kHz`. Sparse three-pixel frames shrank to `7,467` words (`328` blank groups compressed) and reached about `16.3 kHz`. Those results line up with the existing `~560 MB/s` coherent-WC replay ceiling, confirming payload size is now the main lever.
- `2026-03-31`: Refined the blank-group compaction so fully blank groups are omitted from the packed stream entirely unless the whole frame is blank, in which case one minimal blank group is retained to keep the display dark. Local validation: `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba` and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`.
- `2026-03-31`: Remote on `michael@totem1.local`: after omitting blank groups entirely, `64x64 x4`, `parallel=1`, `pwm_bits=11`, `mmio_batch_replays=8` improved again. Dense synthetic frames dropped from `67,392` to `66,816` words and steady resident refresh rose slightly from about `2,088 Hz` to about `2,104 Hz`. Fully black frames dropped from `2,112` words to `6` words and reached about `332.6 kHz`. Sparse three-pixel frames dropped from `7,467` to `5,481` words and rose from about `16.3 kHz` to about `21.1 kHz`. This confirms that eliminating entire blank groups is a real additional win once the kernel loop accepts variable-length packed frames.
- `2026-03-31`: Added `mmio_batch_target_bytes` as an experimental kernel parameter for byte-targeted steady-state batching. Remote on `michael@totem1.local`, a `1 MiB` target did not help dense `64x64 x4` frames (`~2,082 Hz` versus `~2,104 Hz` with fixed `mmio_batch_replays=8`), but it did raise sparse three-pixel frames from about `21.1 kHz` to about `22.2 kHz` and sent the pathological all-black `6`-word frame to multi-megahertz territory. The conclusion is that byte-targeted batching is only worthwhile for extremely small resident payloads, so the Pi was left on the more balanced fixed `mmio_batch_replays=8` default.
- `2026-03-31`: Remote on `michael@totem1.local`: after the payload-compression work, the best fixed `mmio_batch_replays` value shifted upward. For compressed dense `64x64 x4`, `parallel=1`, `pwm_bits=11`, steady resident refresh improved from about `2,019 Hz` at `batch=1` to about `2,104 Hz` at `batch=8`, then plateaued at about `2,112 Hz` for `batch=16` and above. For compressed sparse three-pixel frames, the same sweep climbed from about `14.8 kHz` at `batch=1` to about `22.3 kHz` at `batch=64`. The best practical fixed setting for normal work is now `mmio_batch_replays=16`, which slightly improves dense replay while still helping sparse payloads. The Pi was left loaded with `mmio_batch_replays=16`.
- `2026-03-31`: Added consecutive identical-bitplane merging to the Pi 5 scan packer so adjacent raw groups for the same row pair can collapse into one longer dwell when the shifted pixel payload is identical. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`, and `python -m pytest tests/device/test_rgb_display_pi5_scan_benchmark.py` (skipped locally because `HEART_RUN_PI5_SCAN_TESTS` was unset).
- `2026-03-31`: Added a `solid` Pi 5 scan benchmark pattern to measure flat-color workloads where identical-bitplane merging should pay off. Remote on `michael@totem1.local` via `cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- ...`: `64x64 x4`, `parallel=1`, `pwm_bits=11`, `frame_pattern=dense` stayed at `66,816` words / `~1,995 Hz` with `0` merged groups; `frame_pattern=sparse` dropped to `4,698` words / `~21.2 kHz` with `0` merged groups; `frame_pattern=solid` dropped to `8,352` words with `224` merged groups and reached `~16.6 kHz`; `64x64 x1`, `frame_pattern=solid` dropped to `2,208` words with `224` merged groups and reached `~63.0 kHz`. This confirms the new merge path helps simple flat-color content, while random-like dense frames remain limited by blank-group compression alone.
- `2026-03-31`: Broadened identical-bitplane merging so any duplicate nonblank payload within a row pair coalesces, not just consecutive planes. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`. Remote on `michael@totem1.local` via `cargo run --release --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench -- ...`: with the updated seed-based `frame_pattern=solid`, `64x64 x4`, `parallel=1`, `pwm_bits=11` now packs to `41,760` words with `64` merged groups and replays at `~2,820 Hz`; `frame_pattern=sparse` improved further to `3,915` words with `6` merged groups and `~24.5 kHz`; `frame_pattern=dense` remained at `66,816` words with `0` merged groups and about `1,740 Hz`; `64x64 x1`, `frame_pattern=solid` now packs to `11,040` words with `64` merged groups and reaches `~8.77 kHz`. This confirms the generalized merge helps partially sparse and flat-color scenes, not just all-white frames.
- `2026-03-31`: Retuned the WC MMIO resident-loop batching after the broader payload-merge work. Remote on `michael@totem1.local`, repeated `64x64 x4`, `parallel=1`, `pwm_bits=11` sweeps showed a clear tradeoff: fixed batching (`mmio_batch_replays=16`) held dense frames at about `2,111.7 Hz` and flat-color `solid` frames at about `2,815.6 Hz`, while byte-targeted batching improved tiny sparse frames (`3,915` words) up to about `29.97 kHz`. The best compromise target is `3 MiB`: `mmio_batch_target_bytes=3145728` keeps dense replay effectively tied with fixed `16` (`~2,111.7 Hz`), improves `solid` slightly to about `2,819.6 Hz`, and still keeps sparse replay near `29.7 kHz`. The kernel default is now `3 * 1024 * 1024`, and the Pi was rebuilt/reloaded with that default (`/sys/module/heart_pi5_scan_loop/parameters/mmio_batch_target_bytes = 3145728`).
- `2026-03-31`: Switched the Pi 5 scan data run from one `pull` per column to a 28-bit autopull stream and packed the GPIO pin words densely in Rust while leaving control/count/dwell words as 32-bit pulls. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`. Remote on `michael@totem1.local`, after rebuilding both `heart_pi5_scan_loop.ko` and `pi5_scan_bench`, `64x64 x4`, `parallel=1`, `pwm_bits=11` measured `58,624` words / `~2,392 Hz` for `dense`, `3,435` words / `~28.1 kHz` for `sparse`, and `36,640` words / `~2,652 Hz` for the seed-based `solid` flat-color frame. `64x64 x1`, `dense` dropped to `15,616` words and reached `~7.40 kHz`. This is the first payload reduction in this line of work that improves even the dense case without relying on scene sparsity.
- `2026-03-31`: Retuned the WC MMIO replay batching again after the 28-bit packed-run format landed. On `64x64 x4`, `parallel=1`, `pwm_bits=11`, fixed `16` reached about `2,399.7 Hz` dense / `33.37 kHz` sparse / `3,199.6 Hz` solid, `target=2 MiB` reached about `2,399.7 Hz` dense / `34.03 kHz` sparse / `3,211.6 Hz` solid, `target=3 MiB` reached about `2,391.7 Hz` dense / `33.82 kHz` sparse / `3,195.6 Hz` solid, and `target=4 MiB` reached about `2,413.7 Hz` dense / `34.03 kHz` sparse / `3,219.6 Hz` solid. With the smaller packed transport, `4 MiB` is back to the best overall point, so the kernel default has been restored to `4 * 1024 * 1024` and the Pi was rebuilt/reloaded with `/sys/module/heart_pi5_scan_loop/parameters/mmio_batch_target_bytes = 4194304`.
- `2026-03-31`: Rebased the Pi 5 packed pin words from GPIO bits `0..27` to the actual used `5..27` span, which cuts every shifted pin word from `28` bits to `23` bits without changing semantics because the Adafruit bonnet scan pins all live at GPIO `>= 5`. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`. Remote on `michael@totem1.local`, after rebuilding both `heart_pi5_scan_loop.ko` and `pi5_scan_bench`, `64x64 x4`, `parallel=1`, `pwm_bits=11` dropped to `48,384` words / `~2,898 Hz` for `dense`, `2,835` words / `~38.2 kHz` for `sparse`, and `30,240` words / `~3,528 Hz` for the seed-based `solid` flat-color frame. `64x64 x1`, `dense` dropped to `13,056` words and reached `~9.76 kHz`. This is another structural payload win that helps every retained data run, not just specific color-plane distributions.
- `2026-03-31`: Retuned the WC MMIO replay batching again after the 23-bit rebasing landed. Repeated `64x64 x4`, `parallel=1`, `pwm_bits=11` runs on `michael@totem1.local` showed `target=2 MiB` is now clearly better than fixed `16`: fixed `16` held about `2,911.6 Hz` dense / `40.4 kHz` sparse / `3,871.5 Hz` solid, while `target=2 MiB` reached about `2,919.6 Hz` dense / `41.27 kHz` sparse / `3,891.5 Hz` solid. The kernel default is now `2 * 1024 * 1024`, and the Pi was rebuilt/reloaded with `/sys/module/heart_pi5_scan_loop/parameters/mmio_batch_target_bytes = 2097152`.
- `2026-03-31`: Added a prefix/suffix blank-span trim format for Pi 5 scan groups. Nonblank groups can now omit leading and trailing blank columns by emitting compact blank-span markers around the retained packed data run, while all-blank groups use a minimal `blank -> end -> latch/active/dwell` sequence. This required widening the Rust packer slot sizing and merge logic in `rust/heart_rust/src/runtime/pi5_scan.rs` and updating both PIO programs in `rust/heart_rust/native/pi5_pio_scan_shim.c` and `rust/heart_rust/kernel/pi5_scan_loop/heart_pi5_scan_loop.c` to a 31-instruction parser. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`.
- `2026-03-31`: Remote on `michael@totem1.local`: after rebuilding `heart_pi5_scan_loop.ko` and rerunning `pi5_scan_bench`, the new prefix/suffix trim format kept `mmio_batch_target_bytes=2097152` as the best general setting. On a `200 ms` resident loop, `64x64 x4`, `parallel=1`, `pwm_bits=11` measured about `2,899.1 Hz` dense (`48,032` words), `3,848.8 Hz` solid (`30,560` words), and `685.9 kHz` sparse (`170` words). On a longer `500 ms` steady window with the same module settings, the same workload measured about `2,699.6 Hz` dense, `3,527.2 Hz` solid, and `632.7 kHz` sparse. Compared to the prior 23-bit packed-run format, this keeps dense/solid within a few percent while turning sparse frames into a dramatically smaller resident payload.
- `2026-03-31`: Extended the span-aware packer so it also splits large internal blank gaps inside a nonblank group (`INTERNAL_BLANK_RUN_MIN_PIXELS=5`) instead of only trimming prefix/suffix blanks. Local validation: `cargo fmt --manifest-path rust/heart_rust/Cargo.toml`, `cargo test --manifest-path rust/heart_rust/Cargo.toml pi5_scan_pack_rgba`, and `cargo check --manifest-path rust/heart_rust/Cargo.toml --bin pi5_scan_bench`. Added a new Rust unit case that locks the striped single-panel compression result at `32 * 36` words.
- `2026-03-31`: Remote on `michael@totem1.local`: after syncing the internal-blank splitter and adding a `striped` benchmark pattern, `mmio_batch_target_bytes=2097152` remained the right default. On a `200 ms` resident loop for `64x64 x4`, `parallel=1`, `pwm_bits=11`, the new format measured about `3,238.9 Hz` dense (`43,936` words), `3,848.7 Hz` solid (`30,560` words), `685.9 kHz` sparse (`170` words), and `5,773.2 Hz` striped (`20,160` words). On a longer `500 ms` steady window, dense held about `3,263.6 Hz` and striped about `5,837.2 Hz`. Compared to the prefix/suffix-only pass, this is a real dense-path win too: the synthetic dense frame dropped from `48,032` words / `~2.9 kHz` to `43,936` words / `~3.24 kHz`, while striped/text-like workloads benefit much more strongly.
- `2026-03-31`: Rechecked `mmio_batch_target_bytes` after the internal blank-gap split landed. Remote on `michael@totem1.local`, repeated `200 ms` sweeps for `64x64 x4`, `parallel=1`, `pwm_bits=11` showed dense replay is now essentially flat across the byte-targeted settings while fixed `16` is slightly worse: `target=0` held about `3,199 Hz`, `1 MiB` about `3,239 Hz`, `2 MiB` about `3,239 Hz`, and `4 MiB` about `3,239 Hz`. The new striped workload was similarly flat in the byte-targeted range at about `5.77-5.80 kHz`, with fixed `16` slightly lower at about `5.76 kHz`. The practical conclusion is that the packer change, not another kernel replay knob, was the real win, so the Pi remains on `mmio_batch_target_bytes=2097152`.
