# Heart Repository Agent Instructions

## Installing

Use the tooling in this repository to manage environments. Prefer `uv` for Python dependency resolution.

## Formatting

Run `make format` before committing changes. This applies Ruff fixes, isort, Black, docformatter, and mdformat to Python sources and documentation. Documentation updates should avoid marketing language, state the technical problem in plain terms, and include a materials list when relevant.

- Avoid declaring module-level `__all__` exports. Prefer explicit imports at call sites instead of curating export lists.
- Avoid building filesystem paths via string concatenation. Use `os.path.join` or `pathlib.Path` instead.
- Avoid using `print` for runtime diagnostics in CLI commands; use the shared logger.

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
