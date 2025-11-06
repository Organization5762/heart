# Heart Repository Agent Instructions
## Installing



## Formatting

Run `make format` before committing changes. This will apply Ruff fixes, isort, Black, docformatter, and mdformat to the Python sources and documentation.

## Testing

Run `make test` to execute the Pytest suite located in the `test/` directory. Ensure all tests pass before submitting changes.

When adding tests, it's perfectly reasonable to stub hardware- or framework-heavy dependencies so that the core logic can be exercised in isolation.

## Linting (Optional Pre-Check)

Running `make check` is recommended to verify formatting and linting without applying fixes.

## Documentation Guidelines

If any meaningful changes are made to the runtime architecture or service boundaries, update `docs/code_flow.md` and re-render the diagram via `scripts/render_code_flow.py` so that the documentation stays accurate.

Any meaningfully innovative or thoughtful implementation should be paired with a research note in `docs/research/` that captures the reasoning, trade-offs, or techniques involved.
When you touch areas of the codebase that already have related research notes, skim `docs/research/` to see whether an existing document needs an update or a new companion note.
Research notes should cite the source files or external references that informed the write-up.

Planning documents that live under `docs/planning/` should read like polished facilitation guides. Break the task into well-scoped sub-tasks with checklists, highlight what successful outcomes look like, and use quick-reference diagrams or tables where they clarify the path forward. The `docs/planning/input_event_bus.md` plan illustrates the expected voice and level of detail.
