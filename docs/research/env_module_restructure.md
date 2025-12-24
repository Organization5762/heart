# Environment configuration module restructure

## Summary

The environment configuration helpers now live in focused submodules for parsing, system flags, layout sizing, reactive streams, rendering, color calibration, and asset caching. The `Configuration` facade preserves the `heart.utilities.env` import path while keeping each domain in a smaller file.

## Source references

- `src/heart/utilities/env/config.py`
- `src/heart/utilities/env/parsing.py`
- `src/heart/utilities/env/system.py`
- `src/heart/utilities/env/device_layout.py`
- `src/heart/utilities/env/reactivex.py`
- `src/heart/utilities/env/rendering.py`
- `src/heart/utilities/env/color.py`
- `src/heart/utilities/env/assets.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/ports.py`
- `src/heart/utilities/env/__init__.py`

## Materials

- None
