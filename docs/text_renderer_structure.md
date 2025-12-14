# Text renderer structure

The text renderer now mirrors the layout used by other modular renderers such as Water and Life. Its code lives under `heart/renderers/text/` and is divided into:

- `provider.py`: builds the `TextRenderingState`, wiring the main switch subscription to mutate the state when rotations occur.
- `state.py`: defines the dataclass that stores the current text, font configuration, color, and positional offsets and lazily constructs the pygame font.
- `renderer.py`: contains the rendering logic and uses the provider to initialize state before blitting the centered or positioned text onto the display surface.

Existing imports (`from heart.renderers.text import TextRendering`) remain valid because the new package re-exports the renderer and supporting classes.
