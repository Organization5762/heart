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
