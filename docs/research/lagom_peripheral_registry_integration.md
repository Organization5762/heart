# Lagom peripheral configuration registry injection

## Problem statement

The runtime container created `PeripheralManager` without exposing the shared
`PeripheralConfigurationRegistry`. That made it difficult to validate or
override configuration lookup because the registry instance was hidden inside
the manager and its loader.

## Notes

- Registered `PeripheralConfigurationRegistry` and
  `PeripheralConfigurationLoader` in
  `heart.runtime.container.build_runtime_container` so Lagom can manage shared
  instances for runtime overrides.
- Injected the loader into `PeripheralManager` and surfaced registry access
  through `PeripheralConfigurationLoader.registry` and
  `PeripheralManager.configuration_registry` to support validation and testing.
- Added container coverage in `tests/runtime/test_container.py` to confirm the
  registry instance is shared by the manager and that loader overrides flow
  through the container.

## Materials

- `src/heart/runtime/container.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/peripheral/configuration_loader.py`
- `tests/runtime/test_container.py`
