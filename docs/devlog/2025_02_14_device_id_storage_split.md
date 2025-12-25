# Split persistent device ID storage utilities

## Problem

The serial identity helpers mixed device ID persistence logic with identity query
responses, which made it harder to reason about storage responsibilities in the
firmware I/O layer.

## Change

Device ID persistence utilities now live in `heart.firmware_io.device_id`, while
`heart.firmware_io.identity` focuses on serial identity responses and firmware
commit detection.

## Materials

- `src/heart/firmware_io/device_id.py`
- `src/heart/firmware_io/identity.py`
- `tests/test_device_id.py`
