# Environment configuration module restructure

## Summary

The environment configuration helpers previously lived in a single module. They are now split into focused submodules to keep configuration parsing, enum definitions, and device port discovery separate while preserving the `heart.utilities.env` import path.

## Source references

- `src/heart/utilities/env/config.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/ports.py`
- `src/heart/utilities/env/__init__.py`

## Materials

- None
