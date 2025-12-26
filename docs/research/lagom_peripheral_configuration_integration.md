# Lagom Peripheral Configuration Integration Note

## Problem Statement

The runtime container previously built `PeripheralManager` without injecting the peripheral configuration registry or loader. That made it harder to override configuration loading in tests and obscured how configuration discovery participates in Lagom wiring.

## Materials

- `src/heart/runtime/container.py` for Lagom container bindings.
- `src/heart/peripheral/core/manager.py` for peripheral manager construction.
- `src/heart/peripheral/configuration_loader.py` and `src/heart/peripheral/registry.py` for configuration resolution.
- `tests/runtime/test_container.py` for container override coverage.

## Source Review

- The runtime container binds shared services, including `PeripheralManager`, for dependency resolution.
- `PeripheralManager` uses a `PeripheralConfigurationLoader` to discover and cache configuration factories.
- The loader depends on `PeripheralConfigurationRegistry` to locate configuration modules.

## Integration Notes

The Lagom container now registers `PeripheralConfigurationRegistry` and `PeripheralConfigurationLoader` as singletons before constructing `PeripheralManager`. `PeripheralManager` accepts an injected loader, so tests can override configuration resolution via container overrides without altering runtime wiring. This keeps configuration discovery aligned with the same container that supplies other runtime services.

## Test Notes

The runtime container test suite includes an override check that injects a stub loader and asserts the resolved `PeripheralManager` uses it. This validates that configuration wiring respects container overrides.
