# Combined BPM Screen Provider Property Testing

## Problem statement

State transitions in the combined BPM screen provider depend on elapsed timing data. This update documents the property-based tests that verify the provider switches between metadata and max BPM phases at the configured thresholds so renderer sequencing stays consistent.

## Materials

- `src/heart/renderers/combined_bpm_screen/provider.py`
- `src/heart/renderers/combined_bpm_screen/state.py`
- `tests/renderers/test_combined_bpm_screen_provider.py`
