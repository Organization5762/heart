# Slide transition modes for game mode selection

Game mode selection uses `SlideTransitionRenderer` to move between title scenes. In
some deployments the motion can be distracting or misleading when the knob changes
state quickly. `GameModeState` now supports a static transition mode that keeps the
scenes aligned while still using the slide transition render loop to update and
swap title renderers. The static mode replaces pixels in random order over a fixed
series of masks (defaulting to 20 steps) until scene B fully replaces scene A. A
Gaussian mode uses blurred noise to create softer clustered regions that fade in
over the same step cadence.

## Configuration

Set `transition_mode` on `GameModeState` to control the behavior:

```python
from heart.navigation.game_modes import GameModeState, SlideTransitionMode

state = GameModeState(
    transition_mode=SlideTransitionMode.STATIC,
    static_mask_steps=20,
)
```

`SlideTransitionMode.SLIDE` is the default and preserves left-to-right motion.
`SlideTransitionMode.STATIC` keeps both title scenes aligned and cross-fades via a
random pixel mask over the configured number of steps.

To use Gaussian clusters instead of random pixels:

```python
from heart.navigation.game_modes import GameModeState, SlideTransitionMode

state = GameModeState(
    transition_mode=SlideTransitionMode.GAUSSIAN,
    static_mask_steps=20,
    gaussian_sigma=1.5,
)
```

`SlideTransitionMode.GAUSSIAN` keeps both title scenes aligned and replaces pixels
using a blurred noise mask; increasing `gaussian_sigma` produces larger clusters.

**Materials:**

- Python 3.11+
- `src/heart/navigation/game_modes.py`
- `src/heart/renderers/slide_transition/renderer.py`
