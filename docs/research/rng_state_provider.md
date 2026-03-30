# RNG-aware state providers

The renderer providers that need randomness now store their own
`random.Random` instances directly instead of inheriting from a shared base
class. The old base only assigned one field and exposed it through a property,
which added indirection without reducing real duplication.

## Decision

Keep RNG setup local to each provider. Each provider still accepts an optional
`random.Random` for deterministic tests, but the implementation now stores the
resolved generator on `self._rng` and uses it directly.

## Materials

- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/random_pixel/provider.py`

## Sources

- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/random_pixel/provider.py`
