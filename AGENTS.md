# Heart Repository Agent Instructions

## Installing

Use the tooling in this repository to manage environments. Prefer `uv` for Python dependency resolution.

## Formatting

Run `make format` before committing changes. This applies Ruff fixes, isort, Black, docformatter, and mdformat to Python sources and documentation. Documentation updates should avoid marketing language, state the technical problem in plain terms, and include a materials list when relevant.

- Avoid declaring module-level `__all__` exports. Prefer explicit imports at call sites instead of curating export lists.

## Testing

Run `make test` to execute the Pytest suite located in the `tests/` directory. Ensure all tests pass before submitting changes.

When adding tests, it is reasonable to stub hardware- or framework-heavy dependencies so the core logic can be exercised in isolation.

- Parameterize new Pytest cases when validating multiple input permutations (especially for driver behaviour) to keep coverage
  clear and maintainable.

## Linting (Optional Pre-Check)

Running `make check` is recommended to verify formatting and linting without applying fixes.

## Documentation Guidelines

Update `docs/code_flow.md` and re-render the diagram with `scripts/render_code_flow.py` whenever runtime architecture changes. Pair thoughtful implementations with a research note under `docs/research/` that cites the relevant source files. Plans under `docs/planning/` must follow the structure defined in their `AGENTS.md` file, and contributors should review the master project list in `docs/planning/README.md` before scoping new work. Before implementing a proposal, check `docs/planning/` for related higher-level plans and review any relevant documents.
