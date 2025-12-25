# BLE UART IO buffering update

## Problem

The BLE UART listener currently decodes every incoming chunk into a string and
rebuilds the buffer with string concatenation. That behavior adds extra decode
work and repeated allocations in a hot IO path.

## Observations

The Python JSON loader already accepts byte-oriented payloads:

> Deserialize `s` (a `str`, `bytes` or `bytearray` instance
> containing a JSON document) to a Python object.
> — Python `json.loads` docstring (CPython 3.x)

Python also provides a mutable byte buffer that can be extended in place:

> Construct a mutable bytearray object from:
> — Python `bytearray` docstring (CPython 3.x)

## Implementation approach

- Introduce a reusable `UartMessageBuffer` that can keep payloads as bytes and
  split on a byte delimiter.
- Default BLE UART buffering to the byte strategy and keep the legacy text path
  behind `HEART_BLE_UART_BUFFER_STRATEGY=text` for compatibility.
- Keep the JSON decode and logging behavior in the listener so error handling
  stays centralized.

## Files touched

- `src/heart/peripheral/bluetooth.py`
- `src/heart/peripheral/uart_buffer.py`
- `src/heart/utilities/env/peripheral.py`
- `src/heart/utilities/env/enums.py`

## Materials

- Python standard library `json.loads` docstring (CPython 3.x)
- Python standard library `bytearray` docstring (CPython 3.x)
- Source files listed above
