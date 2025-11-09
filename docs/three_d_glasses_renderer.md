# ThreeDGlassesRenderer

## Overview

`ThreeDGlassesRenderer` remaps static imagery into an LED-friendly
anaglyph so that only red and blue subpixels are energised. The
technique originates from a pairing session with Sri and Michael, and it
is designed for displays that rely on LED glasses or similar colour
filtering hardware.

## How it works

- The renderer loads one or more source images using
  `heart.assets.loader.Loader` and scales them to the device window.
- Each image receives a distinct `_ChannelProfile` that tweaks the
  horizontal offset and balance between the red and blue channels.
- `_apply_profile` converts the source frame to luma, shifts each colour
  channel independently, and writes the result back into the rendering
  surface with the green channel zeroed out.
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

## Hardware notes

Because only the red and blue subpixels are driven, brightness may be
lower than a full-colour scene. Calibrate ambient lighting accordingly
when preparing demos.
