# RNG-aware state providers

State providers that need random numbers were each creating and storing their
own `random.Random` instance. That duplicated setup logic and made it harder to
standardize how providers accept deterministic RNGs for testing.

## Decision

Introduce `RngStateProvider` as a generic base class that stores the RNG and
exposes it through a `rng` property. Providers that already accept an optional
`random.Random` now inherit from the helper and call `super().__init__(rng=...)`
to keep RNG setup consistent.

## Materials

- `src/heart/renderers/state_provider.py`
- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/random_pixel/provider.py`

## Sources

- `src/heart/renderers/state_provider.py`
