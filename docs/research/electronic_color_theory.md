# Electronic Color Theory and the Case for HSV Conversion

## Additive Color on the Device
Our rendering pipeline ultimately drives an emissive RGB (BGR in-memory) panel, so every pixel is emitted light rather than reflected light. Additive color mixing therefore defines the device's gamut: the red, green, and blue primaries accumulate energy to produce perceived hue and brightness. When the Bluetooth hardware controls dial saturation or hue, they are literally scaling how much energy each subpixel contributes.

Working directly in RGB space makes it hard to reason about perceptual changes. A simple gain applied to one channel alters both hue and luminance because each primary contributes to the overall intensity. That is why we take cues from electronic color theory and move into a color model that isolates those dimensions before adjusting the signal.

## Why HSV?
HSV represents colors cylindrically: hue is the angular component, saturation measures distance from the neutral axis, and value captures overall intensity. Unlike RGB, HSV separates chroma from luminance-like information. When we roll the hue knob on the second Bluetooth switch, we need to sweep colors around the spectrum without accidentally desaturating or brightening the image. HSV makes that rotation a simple angle shift while leaving saturation and value untouched.

The device firmware expects BGR frames because of OpenCV's defaults, so we convert to HSV with `cv2.cvtColor`, rotate the hue channel, and then convert back. This roundtrip lets us manipulate hue perceptually while staying compatible with the rest of the rendering stack.

## Implementation Notes
The helper functions `_convert_bgr_to_hsv` and `_convert_hsv_to_bgr` cache small conversion results to avoid recomputing for tiny color edits. Inside `Environment.__finalize_rendering` the hue knob's delta is mapped to roughly eleven degrees per detent before we touch the HSV image. That keeps the hardware control predictable and grounded in color theory: moving the knob means sliding hue along the color wheel, not juggling RGB gains.

By operating in HSV we respect how the human visual system interprets electronic displays. Saturation adjustments still happen in RGB when we intentionally blend toward luminance, but hue-specific edits use HSV so that we only change the attribute the user requested. The conversion cost is small, and the perceptual pay-off—stable brightness, clean saturation, and intuitive hardware controls—is worth the round trip.
