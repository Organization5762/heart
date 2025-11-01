# Heart Agent Guidelines

- If you encounter environment-related failures (missing interpreters, dependency bootstrap issues, etc.) while running commands or tests, investigate and fix the environment instead of skipping the step.
- Prefer solutions that keep local developer workflows reliable (e.g., ensure virtualenv setup commands work without manual intervention).

## Formatting
Run `make format` before committing changes. This will apply Ruff fixes, isort, Black, docformatter, and mdformat to the Python sources and documentation.

## Testing
Run `make test` to execute the Pytest suite located in the `test/` directory. Ensure all tests pass before submitting changes.

## Linting (Optional Pre-Check)
Running `make check` is recommended to verify formatting and linting without applying fixes.
