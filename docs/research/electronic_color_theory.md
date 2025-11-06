# Electronic Color Theory and HSV Conversion

## Problem Statement

Explain why the Heart runtime converts RGB frames to HSV when applying hue controls from Bluetooth peripherals.

## Materials

- Emissive RGB LED panel with BGR memory layout.
- Bluetooth hardware exposing hue and saturation adjustments.
- OpenCV or equivalent library providing RGB↔HSV conversion.

## Technical Approach

1. Model the display as an additive RGB device and identify how per-channel gains affect perceived hue and luminance.
1. Evaluate HSV as an intermediate colour space that isolates hue from brightness and saturation.
1. Implement conversion helpers that round-trip frames through HSV when hue adjustments occur.

## Findings

- Direct RGB scaling entangles hue and luminance, making hardware controls unpredictable.
- HSV represents colours cylindrically, allowing hue rotation without changing saturation or value.
- OpenCV's `cv2.cvtColor` handles the BGR↔HSV conversions with negligible overhead when cached.

## Implementation Notes

- `_convert_bgr_to_hsv` and `_convert_hsv_to_bgr` cache intermediate results for small edits.
- `Environment.__finalize_rendering` maps hardware knob detents to ~11° hue rotations before converting back to BGR.
- Saturation adjustments remain in RGB when blending toward luminance; hue-specific edits rely on HSV to avoid brightness drift.

## Conclusion

Operating in HSV respects additive colour theory on emissive displays and keeps hardware hue controls perceptually stable. The conversion overhead is minimal compared to the benefit of isolating hue from intensity.
