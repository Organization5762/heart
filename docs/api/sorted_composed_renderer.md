# Sorted composed renderer

`heart.navigation.SortedComposedRenderer` extends the existing composition
behaviour to let a callback decide the ordering of child renderers for each
frame. This keeps layering decisions close to runtime data such as peripheral
input or telemetry.

## Basic usage

```python
from heart.navigation import SortedComposedRenderer

composer = SortedComposedRenderer(
    renderers=[background, overlay, hud],
    sorter=lambda renderers, _: sorted(renderers, key=lambda r: r.name),
)
```

`SortedComposedRenderer` expects the sorter to return all renderers that were
passed to the composer. Returning fewer or duplicate values raises a
`ValueError`, protecting against accidental drops or repeats.

## Peripheral-driven ordering

`heart.navigation.switch_controlled_renderer_order` demonstrates how to wire the
rotary switch into ordering decisions. It sorts renderers alphabetically, flips
the stack when the button is pressed, and rotates the list using the current
rotational offset.

```python
from heart.navigation import SortedComposedRenderer, switch_controlled_renderer_order

composer = SortedComposedRenderer(
    [alpha_renderer, beta_renderer, gamma_renderer],
    sorter=switch_controlled_renderer_order,
)
```

The `sorted_composer_demo` program configuration wires this renderer into the
loop so the behaviour can be exercised directly with hardware.
