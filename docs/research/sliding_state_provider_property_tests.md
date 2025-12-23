# Sliding state provider property tests

## Summary

Document the property-based checks added to keep sliding renderer state transitions consistent. The tests focus on width selection and offset wraparound so renderers continue to scroll predictably.

## Materials

- `src/heart/renderers/sliding_image/provider.py`
- `src/heart/renderers/sliding_image/state.py`
- `tests/renderers/test_sliding_state_provider.py`
