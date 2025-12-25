# Life Rule Table Application

## Purpose

Document the rule-table option used by the Life renderer and the conditions that trigger fallbacks to the direct boolean rules.

## Materials

- `src/heart/renderers/life/state.py` for `LIFE_RULE_TABLE` and the rule-application helpers.
- `src/heart/utilities/env/rendering.py` for `HEART_LIFE_RULE_STRATEGY` configuration.
- `tests/modules/test_life_state.py` for parity and fallback coverage.

## Notes

- The rule table is a 2x9 array where rows represent dead/alive cells and columns represent neighbor counts.
- Table lookups are used when the default kernel is active and neighbor counts stay within the 0-8 range.
- If a custom kernel is supplied or the neighbor count falls outside the supported range, the implementation
  falls back to the direct boolean rule application so updates remain safe and predictable.
