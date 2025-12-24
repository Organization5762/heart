# Device package refactor

## Summary

- Reorganized `heart.device` implementations into per-device subpackages to keep device-specific helpers colocated with their implementation.
- Extracted Beats websocket helpers, local display resolution detection, and RGB matrix worker/sample helpers into dedicated modules within their device folders.

## Materials

- `src/heart/device/README.md`
- `src/heart/device/beats/device.py`
- `src/heart/device/beats/websocket.py`
- `src/heart/device/local/device.py`
- `src/heart/device/local/resolution.py`
- `src/heart/device/rgb_display/device.py`
- `src/heart/device/rgb_display/sample_base.py`
- `src/heart/device/rgb_display/worker.py`
- `src/heart/device/rgb_display/isolated_render.py`
- `src/heart/device/single_led/device.py`
- `src/heart/utilities/env.py`
