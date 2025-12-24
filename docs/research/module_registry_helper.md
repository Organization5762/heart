# Module registry helper extraction

## Summary

Registry discovery logic is now centralized in a shared helper so configuration registries reuse the same import/scan behavior. This keeps each registry focused on its specific configuration type while improving consistency and clarity.

## Source references

- `src/heart/utilities/module_registry.py`
- `src/heart/programs/registry.py`
- `src/heart/peripheral/registry.py`

## Materials

- None
