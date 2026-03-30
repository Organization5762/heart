# Shared randomness provider

The renderer providers that need randomness now depend on a shared
`RandomnessProvider` instead of inheriting from a shared base class or
reaching into environment configuration on their own. The old base only
assigned one field and exposed it through a property, which added
indirection without reducing real duplication.

## Decision

Keep RNG setup local to each provider, but require an injected
`RandomnessProvider` so the dependency is visible in the graph. The provider
uses the shared project seed when one is configured, does not namespace RNGs
by default, and still allows opt-in namespacing when a caller needs it. Each
state provider still accepts an optional `random.Random` for deterministic
tests, but the normal runtime path comes through `RandomnessProvider`.

## Materials

- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/random_pixel/provider.py`
- `src/heart/peripheral/providers/randomness/provider.py`

## Sources

- `src/heart/peripheral/providers/randomness/provider.py`
- `src/heart/renderers/pacman/provider.py`
- `src/heart/renderers/pixels/provider.py`
- `src/heart/renderers/random_pixel/provider.py`
