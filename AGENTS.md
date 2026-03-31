# Heart Repository Agent Instructions

## Installing

Use the tooling in this repository to manage environments. Prefer `uv` for Python dependency resolution.

- Pin prerelease Python dependencies with exact versions in `pyproject.toml` so `uv.lock` resolves the intended alpha or beta release.
- `experimental/beats` test and lint commands require that workspace's Node dependencies to be installed first; `npm exec` alone is not enough because the Vite/Vitest config imports project-local plugins such as `@vitejs/plugin-react`.
- When `experimental/beats/package-lock.json` is out of sync with `package.json`, `npm ci` will fail; use `npm install --package-lock=false` for local validation unless the task explicitly includes repairing the lockfile, and use `npm install` when the task does include resyncing the lockfile.
- Scene and asset bootstrap can run before `pygame.display.set_mode`; avoid unconditional `convert()` or `convert_alpha()` calls in asset constructors and defer display-dependent conversion until a surface exists.
- `DisplayContext` wraps the active `pygame.Surface`; renderers that need surface-only APIs such as `subsurface()` must use `window.screen` after confirming it is initialized instead of calling those APIs on `DisplayContext` directly.
- Only the real display-owned `DisplayContext` may change pygame display modes; scratch or post-processing contexts must keep `can_configure_display=False` and never call `pygame.display.set_mode()`.
- OpenGL-backed renderers must treat `reset()` as lifecycle teardown: cascade reset into nested runtimes and restore mutated UI state such as mouse visibility so mode switches can leave GPU-backed scenes cleanly.
- Vite `.mts` configs that are shared with Storybook or other native-ESM tooling must derive `__dirname` via `fileURLToPath(new URL(".", import.meta.url))` instead of relying on the CommonJS global.

## Formatting

Run `make format` before committing changes. This applies Ruff fixes, isort, Black, docformatter, and mdformat to Python sources and documentation. Documentation updates should avoid marketing language, state the technical problem in plain terms, and include a materials list when relevant.

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
- For pygame-bound Rx delivery, use the explicit frame-thread handoff in `heart.utilities.reactivex_threads` and drain it from `PeripheralRuntime.tick()` instead of treating a scheduler as the game loop thread.
- Prefer module-level constants for tunable loop intervals instead of embedding sleep literals in long-running loops.
- Prefer module-level constants for retry thresholds in reconnect or recovery loops instead of inline numeric literals.
- Use `time.monotonic()` for elapsed-time comparisons, and reserve `time.time()` for wall-clock timestamps that leave the process.
- Prefer `pathlib.Path.read_text`/`write_text` helpers for straightforward text file I/O.
- When reading or writing text files, specify an explicit encoding (prefer `utf-8`) to keep behavior consistent across platforms.
- Use module-level constants for public constructor or function default values so shared configuration is easy to discover and adjust.
- When parsing PATH-like environment variables, strip whitespace from each entry and ignore empty values before converting to `Path` objects.
- When a renderer only forwards `builder.observable(peripheral_manager)`, omit the `state_observable()` override and rely on `StatefulBaseRenderer`.
- Keep post-processors lifecycle-local; avoid provider/state dataclass scaffolding unless the post-processor actually subscribes to streams.
- Use module-level constants for default argument values and shared string literals in firmware helpers so configuration stays consistent.
- Keep mixed PyO3 packages in a `rust/<package>/` layout with the Rust crate in `src/`, Python shims in `python/<package>/`, and a private native submodule exposed via `tool.maturin.module-name` to avoid import ambiguity.
- PyO3 stub-generation binaries require a linkable Python 3.11 runtime in addition to Rust; if `cargo run --bin stub_gen` fails with unresolved `Py*` symbols, install or point PyO3 at a Python 3.11 build before retrying.

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

## Environment Cleanup

If a single file or module starts accumulating setup, orchestration, configuration, and cleanup logic, move those responsibilities into smaller, focused modules or helpers so each file handles fewer concerns and is easier to reason about.

## Configuration Defaults

Define CLI default values as module-level constants so they stay consistent across commands and are easy to review.

## Validation

- `make format`
- `make test`

## Recent Validation

- `2026-03-31`: `cd experimental/beats && npm install --package-lock=false`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/prettier --write src/actions/ws/providers/PeripheralEventsProvider.tsx src/tests/unit/actions/ws/peripheral_events_provider.test.tsx`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/eslint src/actions/ws/providers/PeripheralEventsProvider.tsx src/tests/unit/actions/ws/peripheral_events_provider.test.tsx`
- `2026-03-31`: `experimental/beats: npm run test -- --run src/tests/unit/actions/ws/peripheral_events_provider.test.tsx`
- `2026-03-31`: `rg -n "Sitemap|siteMap|usgc-ascii-map" experimental/beats/src/routes/index.tsx` returned no matches after removing the Beats home-page sitemap.
- `2026-03-31`: `cd experimental/beats && ./node_modules/.bin/prettier --check src/routes/index.tsx` could not run because this worktree does not currently have `experimental/beats/node_modules` installed.
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/prettier --write src/components/usgc.tsx src/routes/index.tsx` failed because this worktree does not currently have `experimental/beats/node_modules`.
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/eslint src/components/usgc.tsx src/routes/index.tsx` failed because this worktree does not currently have `experimental/beats/node_modules`.
- `2026-03-31`: `pytest tests/device/test_beats_websocket.py`
- `2026-03-31`: `cd experimental/beats && npm install`
- `2026-03-31`: `cd experimental/beats && npm ci`
- `2026-03-31`: `cd experimental/beats && npm install --package-lock=false`
- `2026-03-31`: `cd experimental/beats && npx prettier --write .storybook/main.ts .storybook/preview.tsx src/components/ui/button.stories.tsx src/components/stream-cube.stories.tsx README.md package.json tsconfig.json vite.renderer.config.mts vite.main.config.mts`
- `2026-03-31`: `cd experimental/beats && npx eslint .storybook/main.ts .storybook/preview.tsx src/components/ui/button.stories.tsx src/components/stream-cube.stories.tsx vite.renderer.config.mts vite.main.config.mts`
- `2026-03-31`: `cd experimental/beats && npm run test`
- `2026-03-31`: `cd experimental/beats && npm run build-storybook`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/15a4/heart/.uv-cache .venv/bin/pytest tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/15a4/heart/.uv-cache make format`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/15a4/heart/.uv-cache make test`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/14cd/heart/.uv-cache make format`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/14cd/heart/.uv-cache make test`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/14cd/heart/.uv-cache make format` after removing `BaseRenderer`, the `AtomicBaseRenderer.process()` compatibility path, and the unused renderer `warmup` flag.
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/14cd/heart/.uv-cache make test` after removing `BaseRenderer`, the `AtomicBaseRenderer.process()` compatibility path, and the unused renderer `warmup` flag.
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
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make format`
- `2026-03-30`: `.venv/bin/python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `.venv/bin/pytest tests/navigation/test_game_modes.py tests/runtime/test_display_context.py tests/runtime/test_container.py tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_multi_scene_resolution.py tests/renderers/test_combined_bpm_screen_resolution.py tests/utilities/test_env.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make format` after removing unused rendering env knobs and the orphaned runtime timing helper.
- `2026-03-30`: `.venv/bin/pytest tests/utilities/test_env.py tests/test_environment_core_logic.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/python scripts/render_code_flow.py --output docs/code_flow.svg` after resolving merge conflicts across the runtime architecture docs and generator.
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make format` after resolving merge conflicts in `GameModes`, runtime container wiring, and environment tests.
- `2026-03-30`: `.venv/bin/pytest tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make format` failed because `uvx` could not write under `/Users/lampe/.local/share/uv/tools/.tmppRsW2Z` in this sandbox.
- `2026-03-30`: `.venv/bin/isort packages src tests`
- `2026-03-30`: `.venv/bin/ruff check --fix packages src tests`
- `2026-03-30`: `.venv/bin/docformatter -i -r --config ./pyproject.toml docs`
- `2026-03-30`: `.venv/bin/mdformat docs`
- `2026-03-30`: `.venv/bin/pytest tests/runtime/test_container.py tests/runtime/test_game_loop.py tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_multi_scene_resolution.py tests/test_environment_core_logic.py tests/display/test_screen_recorder.py tests/renderers/test_combined_bpm_screen_resolution.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/python scripts/render_code_flow.py --output docs/code_flow.svg` after updating `scripts/render_code_flow.py` for the `GameModes`/`ComposedRenderer` topology.
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test` after the final docstring-only test update.
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
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make format` failed because `uvx` could not write under `/Users/lampe/.local/share/uv/tools/.tmpNK8ajn` in this sandbox.
- `2026-03-30`: `.venv/bin/isort packages src tests`
- `2026-03-30`: `.venv/bin/ruff check --fix packages src tests`
- `2026-03-30`: `.venv/bin/docformatter -i -r --config ./pyproject.toml docs`
- `2026-03-30`: `.venv/bin/mdformat docs`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/prettier --write src/actions/peripherals/event_list.tsx src/actions/peripherals/peripheral_snapshots.tsx src/actions/peripherals/peripheral_tree.tsx src/actions/ws/providers/ImageProvider.tsx src/actions/ws/providers/PeripheralEventsProvider.tsx src/actions/ws/providers/PeripheralProvider.tsx src/components/app-sidebar.tsx src/components/stream-cube.tsx src/components/stream.tsx src/components/ui/button.tsx src/components/ui/input.tsx src/components/ui/peripherals/accelerometer.tsx src/components/ui/peripherals/rotary_button.tsx src/components/ui/peripherals/uwb_positioning.tsx src/components/ui/sidebar.tsx src/components/ui/toggle.tsx src/components/usgc.tsx src/hooks/use-mobile.ts src/layouts/base-layout.tsx src/renderer.ts src/routes/index.tsx src/routes/mission-control/index.tsx src/routes/peripherals/connected.tsx src/routes/peripherals/events.tsx src/routes/peripherals/snapshots.tsx src/styles/global.css src/types.d.ts tsconfig.json`
- `2026-03-31`: `experimental/beats: npm run lint`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/tsc --noEmit`
- `2026-03-31`: `experimental/beats: npm run test -- --passWithNoTests` (no Vitest files matched)
- `2026-03-31`: No validation run after updating `experimental/beats/src/features/stream-console/scene-config.ts` to keep the Current Stream cube fixed by default and slightly increase the default camera distance; these were small config-only changes.
- `2026-03-31`: `cd experimental/beats && npm ci` failed because `experimental/beats/package-lock.json` is out of sync with `package.json`.
- `2026-03-31`: `cd experimental/beats && npm install --package-lock=false`
- `2026-03-31`: `cd experimental/beats && npm run format:write`
- `2026-03-31`: `cd experimental/beats && npx eslint src/components/stream-cube.tsx src/components/stream.tsx src/tests/unit/components/stream.test.tsx src/tests/unit/setup.ts`
- `2026-03-31`: `cd experimental/beats && npm run lint` still fails because of pre-existing errors in `src/actions/ws/providers/PeripheralEventsProvider.tsx`, `src/actions/ws/providers/PeripheralProvider.tsx`, `src/components/ui/sidebar.tsx`, `src/hooks/use-mobile.ts`, and `src/layouts/base-layout.tsx`.
- `2026-03-31`: `cd experimental/beats && npm run test`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/535d/heart/.uv-cache make format`
- `2026-03-31`: `experimental/beats: npm install --package-lock=false`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/prettier --write src/actions/peripherals/peripheral_tree.tsx src/components/peripheral-sensor-deck.tsx src/components/ui/peripherals/generic_sensor.tsx src/routes/peripherals/connected.tsx src/tests/unit/components/generic_sensor.test.ts`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/eslint src/actions/peripherals/peripheral_tree.tsx src/components/peripheral-sensor-deck.tsx src/components/ui/peripherals/generic_sensor.tsx src/routes/peripherals/connected.tsx src/tests/unit/components/generic_sensor.test.ts`
- `2026-03-31`: `experimental/beats: npm run test -- src/tests/unit/components/generic_sensor.test.ts src/tests/unit/components/stream.test.tsx`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/535d/heart/.uv-cache make test`
- `2026-03-31`: `npm install` in `experimental/beats` to resync `package-lock.json` after `npm ci` failed because the lockfile was missing `protobufjs` and related transitive dependencies.
- `2026-03-31`: `./node_modules/.bin/prettier --write src/components/stream.tsx src/components/stream-cube.tsx src/components/scene-plugin-dock.tsx src/components/sensor-lab-panel.tsx src/components/sensor-history-chart.tsx src/features/stream-console/sensor-simulation.ts src/features/stream-console/use-sensor-simulation.ts` in `experimental/beats`
- `2026-03-31`: `./node_modules/.bin/eslint src/components/stream.tsx src/components/stream-cube.tsx src/components/scene-plugin-dock.tsx src/components/sensor-lab-panel.tsx src/components/sensor-history-chart.tsx src/features/stream-console/scene-config.ts src/features/stream-console/sensor-simulation.ts src/features/stream-console/use-sensor-simulation.ts src/tests/unit/features/stream-console/sensor-simulation.test.ts` in `experimental/beats`
- `2026-03-31`: `./node_modules/.bin/prettier --check src/components/stream.tsx src/components/stream-cube.tsx src/components/scene-plugin-dock.tsx src/components/sensor-lab-panel.tsx src/components/sensor-history-chart.tsx src/features/stream-console/scene-config.ts src/features/stream-console/sensor-simulation.ts src/features/stream-console/use-sensor-simulation.ts src/tests/unit/features/stream-console/sensor-simulation.test.ts` in `experimental/beats`
- `2026-03-31`: `npm run test -- src/tests/unit/features/stream-console/sensor-simulation.test.ts` in `experimental/beats`
- `2026-03-31`: `./node_modules/.bin/tsc --noEmit` in `experimental/beats` still fails because of pre-existing TypeScript issues in the app and its dependencies, including `@electron-forge/plugin-vite` types, the protobuf `?raw` import declaration, existing route typing drift, and unrelated component typing errors outside the new stream-console files.
- `2026-03-31`: `cd experimental/beats && npm install --package-lock=false`
- `2026-03-31`: `cd experimental/beats && ./node_modules/.bin/prettier --write src/components/stream.tsx src/components/scene-plugin-dock.tsx src/components/sensor-lab-panel.tsx src/components/sensor-history-chart.tsx src/styles/global.css`
- `2026-03-31`: `cd experimental/beats && ./node_modules/.bin/eslint src/components/stream.tsx src/components/scene-plugin-dock.tsx src/components/sensor-lab-panel.tsx src/components/sensor-history-chart.tsx`
- `2026-03-31`: `cd experimental/beats && npm run test -- --run src/tests/unit/components/stream.test.tsx src/tests/unit/features/stream-console/sensor-simulation.test.ts`
- `2026-03-30`: `.venv/bin/pytest tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make format`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/e46a/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/ruff check --fix tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/pytest tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/isort src/heart/peripheral/core/streams.py src/heart/peripheral/core/manager.py src/heart/peripheral/core/input/profiles/navigation.py src/heart/navigation/game_modes.py tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/peripheral/core/streams.py src/heart/peripheral/core/manager.py src/heart/peripheral/core/input/profiles/navigation.py src/heart/navigation/game_modes.py tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `.venv/bin/pytest tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/peripheral/core/input/profiles/navigation.py src/heart/peripheral/core/input/profiles/mandelbrot.py src/heart/renderers/mandelbrot/control_mappings.py src/heart/peripheral/core/input/__init__.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/peripheral/core/input/profiles/navigation.py src/heart/peripheral/core/input/profiles/mandelbrot.py src/heart/renderers/mandelbrot/control_mappings.py src/heart/peripheral/core/input/__init__.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/pytest tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py tests/renderers/test_provider_signatures.py tests/runtime/test_container.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/isort src/heart/peripheral/keyboard.py src/heart/peripheral/core/input/keyboard.py src/heart/peripheral/core/input/gamepad.py src/heart/peripheral/core/input/__init__.py src/heart/peripheral/switch.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/ruff check --fix src/heart/peripheral/keyboard.py src/heart/peripheral/core/input/keyboard.py src/heart/peripheral/core/input/gamepad.py src/heart/peripheral/core/input/__init__.py src/heart/peripheral/switch.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/pytest tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py tests/renderers/test_provider_signatures.py tests/runtime/test_container.py`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make format` failed because `uvx` could not write under `/Users/lampe/.local/share/uv/tools/.tmpmtFWG0` in this sandbox.
- `2026-03-30`: `.venv/bin/isort packages src tests`
- `2026-03-30`: `.venv/bin/ruff check --fix packages src tests`
- `2026-03-30`: `.venv/bin/docformatter -i -r --config ./pyproject.toml docs`
- `2026-03-30`: `.venv/bin/mdformat docs`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/pytest tests/peripheral/test_input_core.py tests/navigation/test_game_modes.py tests/runtime/test_container.py`
- `2026-03-30`: `.venv/bin/isort packages src tests`
- `2026-03-30`: `.venv/bin/ruff check --fix packages src tests`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-30`: `.venv/bin/pytest tests/utilities/test_reactivex_threads.py tests/peripheral/test_switch.py tests/peripheral/test_input_core.py tests/utilities/test_env.py`
- `2026-03-30`: `.venv/bin/isort src/heart/utilities/reactivex_threads.py src/heart/runtime/peripheral_runtime.py src/heart/utilities/env/reactivex.py src/heart/utilities/env/enums.py src/heart/utilities/env/__init__.py src/heart/peripheral/core/input/debug.py src/heart/peripheral/core/input/frame.py src/heart/peripheral/core/input/keyboard.py src/heart/peripheral/core/input/gamepad.py src/heart/peripheral/core/input/accelerometer.py src/heart/peripheral/core/input/profiles/navigation.py src/heart/peripheral/core/input/profiles/mandelbrot.py src/heart/peripheral/keyboard.py src/heart/peripheral/switch.py src/heart/peripheral/sensor.py src/heart/peripheral/phyphox.py tests/utilities/test_env.py tests/utilities/test_reactivex_threads.py tests/peripheral/test_switch.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `.venv/bin/ruff check src/heart/utilities/reactivex_threads.py src/heart/runtime/peripheral_runtime.py src/heart/utilities/env/reactivex.py src/heart/utilities/env/enums.py src/heart/utilities/env/__init__.py src/heart/peripheral/core/input/debug.py src/heart/peripheral/core/input/frame.py src/heart/peripheral/core/input/keyboard.py src/heart/peripheral/core/input/gamepad.py src/heart/peripheral/core/input/accelerometer.py src/heart/peripheral/core/input/profiles/navigation.py src/heart/peripheral/core/input/profiles/mandelbrot.py src/heart/peripheral/keyboard.py src/heart/peripheral/switch.py src/heart/peripheral/sensor.py src/heart/peripheral/phyphox.py tests/utilities/test_env.py tests/utilities/test_reactivex_threads.py tests/peripheral/test_switch.py tests/peripheral/test_input_core.py`
- `2026-03-30`: `python scripts/render_code_flow.py --output docs/code_flow.svg`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make format` failed because `uvx` could not write under `/Users/lampe/.local/share/uv/tools/.tmp65S17D` in this sandbox.
- `2026-03-30`: `.venv/bin/isort packages src tests`
- `2026-03-30`: `.venv/bin/ruff check --fix packages src tests`
- `2026-03-30`: `.venv/bin/docformatter -i -r --config ./pyproject.toml docs`
- `2026-03-30`: `.venv/bin/mdformat docs`
- `2026-03-30`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/94af/heart/.uv-cache make test`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/3af3/heart/.uv-cache make format`
- `2026-03-31`: `experimental/beats: npm install --package-lock=false`
- `2026-03-31`: `experimental/beats: ./node_modules/.bin/prettier --write src/components/stream.tsx src/components/stream-console-header.tsx src/components/stream-visual-mixer-panel.tsx src/components/stream-footer-bar.tsx`
- `2026-03-31`: `experimental/beats: npm run test -- src/tests/unit/components/stream.test.tsx`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/3af3/heart/.uv-cache .venv/bin/pytest tests/device/test_beats_websocket.py tests/runtime/test_peripheral_runtime.py`
- `2026-03-31`: `npm test -- --run src/tests/unit/actions/ws/websocket.test.tsx` in `experimental/beats` failed because `vitest` was not installed in that workspace (`node_modules` missing).
- `2026-03-31`: `npm exec vitest run src/tests/unit/actions/ws/websocket.test.tsx` in `experimental/beats` failed because the workspace dependencies were not installed, so `@vitejs/plugin-react` could not be resolved from `vitest.config.ts`.
- `2026-03-31`: `cd experimental/beats && npm run format:write`
- `2026-03-31`: `cd experimental/beats && npm run lint`
- `2026-03-31`: `cd experimental/beats && ./node_modules/.bin/tsc --noEmit`
- `2026-03-31`: `cd experimental/beats && npm run test`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/ef33/heart/.uv-cache make format`
- `2026-03-31`: `UV_CACHE_DIR=/Users/lampe/.codex/worktrees/ef33/heart/.uv-cache make test`
