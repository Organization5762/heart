# Life Rule Lookup Table

## Context

The Life renderer now supports applying the Game of Life rules via a lookup table in
`heart.renderers.life.state.LifeState` when the default kernel is in use. The table
encodes the standard B3/S23 rules for neighbor counts 0-8 so the update step can avoid
repeated boolean comparisons while preserving identical outcomes.

## Table Layout

The table is a 2x9 integer array indexed by `[current_state, neighbor_count]`:

- `current_state=0` (dead) only produces a live cell when `neighbor_count=3`.
- `current_state=1` (alive) stays alive when `neighbor_count` is 2 or 3.

This mapping is implemented in `src/heart/renderers/life/state.py` as `LIFE_RULE_TABLE`
and applied through `_apply_table_rules`.

## Fallback Behavior

When custom kernels are used, the neighbor counts may exceed 8. In that case the update
logic falls back to direct rule evaluation so the Life rules remain accurate regardless
of kernel shape or weighting. Tests in `tests/modules/test_life_state.py` validate that
table-driven rules match the direct path and that custom kernels are handled safely.

## Materials

- `src/heart/renderers/life/state.py` for the rule table and application logic.
- `src/heart/utilities/env/rendering.py` for environment configuration.
- `tests/modules/test_life_state.py` for parity and fallback coverage.
