# ThreeDGlassesRenderer

## Overview

`ThreeDGlassesRenderer` remaps static imagery into an LED-friendly
anaglyph so that the red lens sees a warm-tinted offset while the cyan
lens receives a matching counterpart. The
technique originates from a pairing session with Sri and Michael, and it
is designed for displays that rely on LED glasses or similar colour
filtering hardware.

## How it works

- The renderer loads one or more source images using
  `heart.assets.loader.Loader` and scales them to the device window.
- Each image receives a distinct `_ChannelProfile` that tweaks the
  horizontal offset and balance between the red and cyan channels to
  emphasise parallax cues on 64×64 content.
- `_apply_profile` blends the source frame into warm (left-eye) and cool
  (right-eye) views, shifts them in opposite directions, and writes the
  result back into the rendering surface with the cyan tint duplicated
  across green and blue.
- Frames advance on a configurable cadence (default `650ms`) using the
  renderer clock, so viewers perceive alternating depth cues when
  looking through LED glasses.

## Usage

```python
from heart.display.renderers.three_d_glasses import ThreeDGlassesRenderer

renderer = ThreeDGlassesRenderer([
    "gallery/left_panel.png",
    "gallery/right_panel.png",
])
```

Integrate the renderer into a program configuration the same way you
would add any other `BaseRenderer` subclass.

## Program configuration

`heart/programs/configurations/three_d_glasses_demo.py` wires the
renderer into the runtime with the stock `heart.png` assets. Launch it
with:

```bash
totem run --configuration three_d_glasses_demo
```

The configuration adds a single mode so the demo starts immediately in
the 3D view.

## Hardware notes

Because only the red and blue subpixels are driven, brightness may be
lower than a full-colour scene. Calibrate ambient lighting accordingly
when preparing demos.
