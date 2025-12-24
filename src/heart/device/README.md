Device abstractions for rendering targets. Classes here describe the physical layout of displays (rectangular panels or cubes) and provide device-specific interfaces for sending frames to LEDs or simulated outputs.

Each device now lives in its own subpackage (for example, `beats/`, `local/`, `rgb_display/`,
and `single_led/`) with support helpers colocated alongside the device implementation.
