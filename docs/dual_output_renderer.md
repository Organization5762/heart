# Dual Output Renderer Example

## Overview

This example demonstrates how a single `GameLoop` fan-outs its rendered frame
to both the primary LED matrix and a secondary 1×1 LED device. The mirror LED
derives its colour from the average hue of the matrix frame, allowing a small
indicator to reflect the aggregate brightness of the main scene.

## Components

- `heart.device.single_led.SingleLEDDevice` – in-memory device representing a
  single addressable LED pixel.
- `heart.peripheral.average_color_led.AverageColorLED` – peripheral that
  subscribes to the LED matrix display frames and updates the single LED with
  the average colour.
- `heart.programs.configurations.dual_output_demo` – configuration that wires
  the mirror peripheral into the default render loop.

## Running the configuration

```bash
totem run --configuration dual_output_demo
```

The CLI bootstraps the primary `GameLoop`, renders the configured colour
through the matrix drivers, and publishes each frame to the
`LEDMatrixDisplay` peripheral. `AverageColorLED` listens for these frame events
and renders the average colour to the single LED device. In a hardware setup
this secondary device can drive a dedicated indicator LED or any controller
that accepts 1×1 RGB frames.

## Testing

The Pytest suite includes targeted coverage in
`tests/peripheral/test_average_color_led.py` ensuring the mirror peripheral
tracks only the intended producer and correctly computes the mean colour from
mixed frames. `tests/test_environment.py` additionally validates that multiple
`GameLoop` instances can coexist when coordinating multi-device output.
