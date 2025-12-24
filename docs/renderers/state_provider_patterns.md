# Renderer state provider patterns

## Problem statement

Some renderers only need a single immutable state snapshot, while others need a
stream of updates driven by peripherals. Keeping one-off provider classes for
static state adds boilerplate and makes it harder to see which configuration
values are intended to be stateful.

## Static state providers

Use `heart.peripheral.core.providers.StaticStateProvider` when a renderer only
needs one state snapshot and does not subscribe to live updates. This provider
emits the state once and shares the observable for repeated subscriptions.

Example usage with `StatefulBaseRenderer`:

```python
from heart.renderers import StatefulBaseRenderer
from heart.peripheral.core.providers import StaticStateProvider

state = RenderColorState(color=Color(255, 0, 0))
renderer = RenderColor(state=state)
```

`StatefulBaseRenderer` accepts a concrete `state` argument and will wrap it with
`StaticStateProvider` automatically, so most renderers do not need to reference
`StaticStateProvider` directly.

## Streaming state providers

When state should evolve over time, continue to use providers that return a
stream driven by `PeripheralManager`. Seed the provider with an initial state
that contains any configuration fields (for example, scroll speed) so the
configuration is part of the state snapshot instead of an instance attribute.

## Materials

- `src/heart/peripheral/core/providers/__init__.py` (`StaticStateProvider`)
- `src/heart/renderers/__init__.py` (`StatefulBaseRenderer` state initialization)
- `src/heart/renderers/color/renderer.py` (static state usage)
- `src/heart/renderers/sliding_image/provider.py` (initial state seeding)
