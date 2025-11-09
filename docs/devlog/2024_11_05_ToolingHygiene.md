# Tooling hygiene adjustments

## Summary

- Configure `mypy` to emit compact, line-oriented diagnostics without color or context blocks by updating `pyproject.toml`.
- Remove module-level `__all__` declarations across packages to favor explicit imports.

## Impacted modules

- `pyproject.toml`
- `src/heart/events/*`
- `src/heart/peripheral/*`
- `src/heart/display/recorder.py`
- `tests/events/test_metrics.py`
- `tests/simulation/__init__.py`
- `experimental/isolated_rendering/*`
- `experimental/peripheral_sidecar/*`

These adjustments align repository guidance with current linting expectations and simplify future tooling automation.
