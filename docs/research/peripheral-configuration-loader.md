# Peripheral configuration loading refactor

## Problem statement

The peripheral manager handled configuration resolution, registry lookup, and detection orchestration in one class. This mixed concerns made the configuration lifecycle harder to follow when reading `PeripheralManager` and obscured the single responsibility of loading a configuration by name.

## Notes

- Moved configuration resolution and caching into `heart.peripheral.configuration_loader.PeripheralConfigurationLoader` so `PeripheralManager` focuses on peripheral orchestration.
- Retained the same configuration selection logic while centralizing the registry lookup and logging in one place.

## Materials

- `src/heart/peripheral/configuration_loader.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/peripheral/registry.py`
