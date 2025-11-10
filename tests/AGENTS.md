# Tests Directory Agent Instructions

## Pytest Conventions

- Organize new tests under the existing subpackages (e.g., `events/`, `navigation/`) rather than introducing new top-level modules unless a new domain is introduced.
- Name test files with the pattern `test_<feature>.py` and ensure every test function and `pytest` class includes the docstrings described in the repository root `AGENTS.md`.
- Prefer parametrized test cases over hand-written loops; use `pytest.mark.parametrize` with explicit argument names and ids that summarize the scenario.
- Use `pytest.mark.asyncio` for coroutine tests and keep async fixtures in `conftest.py` to avoid duplication.

## Fixtures and Helpers

- Reuse fixtures defined in `tests/conftest.py` or `tests/helpers/` before creating new ones. Any new reusable fixture should be added to `conftest.py` with a descriptive docstring covering setup cost and primary use case.
- Place helper utilities shared across multiple domains in `tests/utilities/`. Keep helper names aligned with the behaviour they abstract and avoid test-specific logic in fixtures that should live alongside the production code.
- Centralize environment variable setup in `tests/conftest.py` fixtures so graphical and hardware stubs stay consistent across the suite.

## Assertions and Diagnostics

- Use high-signal assertions that compare full structures (e.g., dataclasses, dictionaries) rather than checking individual fields unless only a subset matters.
- Include meaningful failure messages via `assert` expressions or `pytest.fail()` when validating complex flows so regressions highlight the missing behaviour.
- Attach `capsys`/`caplog` usage to the narrowest scope possible and reset stateful dependencies with context managers to prevent leakage between tests.

## Markers and Test Selection

- Add a `pytest.mark.slow` marker to tests that routinely exceed one second locally, and document the reason in the test docstring.
- Guard hardware or network integrations behind `pytest.mark.integration` and provide a lightweight simulation fallback in `tests/simulation/` when feasible.

## File Expectations

- Keep tests importable without side effects. Avoid executing code at import time beyond fixture and constant declarations.
- Maintain deterministic ordering by avoiding reliance on global mutable state. Prefer factory functions over module-level singletons within tests.
