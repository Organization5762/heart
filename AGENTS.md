# Heart Repository Agent Instructions

## Installing

Use the tooling in this repository to manage environments. Prefer `uv` for Python dependency resolution.

## Formatting

Run `make format` before committing changes. This applies Ruff fixes, isort, Black, docformatter, and mdformat to Python sources and documentation. Documentation updates should avoid marketing language, state the technical problem in plain terms, and include a materials list when relevant.

- Avoid declaring module-level `__all__` exports. Prefer explicit imports at call sites instead of curating export lists.
- Define device identifiers (such as firmware `device_name` values) as module-level constants instead of inline literals.
- Avoid building filesystem paths via string concatenation. Use `os.path.join` or `pathlib.Path` instead.
- Prefer `pathlib.Path` over `os.path.join` when constructing paths, and ensure functions annotated to return a `Path` return a `Path` object.
- When CLI arguments accept file paths, parse them as `pathlib.Path` objects and ensure parent directories exist before writing.
- Avoid using `print` for runtime diagnostics in CLI commands; use the shared logger.
- Avoid using `print` for runtime diagnostics in peripheral modules; use the shared logger.
- Avoid leaving commented debug print statements in production modules; remove them once they are no longer needed.
- Avoid wildcard imports; use explicit imports so dependencies stay clear and tooling can track usage.
- Prefer mixins or composition over direct inheritance.
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
