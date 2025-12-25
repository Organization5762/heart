# Optional import handling

## Problem

Optional dependency imports are handled in multiple ways across the codebase. Some
call sites import a module and then fetch an attribute without a consistent log
path when the attribute is missing. This makes it harder to understand why a
feature is unavailable.

## Approach

Add a helper that returns a requested attribute from an optional dependency and
logs when either the module or the attribute is unavailable. Use it where we
fetch specific attributes from optional modules.

## Impacted areas

- `src/heart/utilities/optional_imports.py` (`optional_import_attribute`)
- `src/heart/peripheral/ir_sensor_array.py` (least-squares lookup)
- `src/heart/firmware_io/bluetooth.py` (BLE class lookups)

## Materials

- `src/heart/utilities/optional_imports.py`
- `src/heart/peripheral/ir_sensor_array.py`
- `src/heart/firmware_io/bluetooth.py`
