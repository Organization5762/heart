# Clean-Room HUB75 Runtime PRD

## Materials

- `src/heart/device/rgb_display/device.py`
- `src/heart/device/rgb_display/worker.py`
- `src/heart/device/selection.py`
- `src/heart/utilities/env/config.py`
- [Adafruit RGB Matrix Bonnet for Raspberry Pi pinouts](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi/pinouts)
- [Adafruit Triple LED Matrix Bonnet for Raspberry Pi with HUB75 pinouts](https://learn.adafruit.com/adafruit-triple-led-matrix-bonnet-for-raspberry-pi-with-hub75/pinouts)
- [Adafruit RGB Matrix Panels With Raspberry Pi 5 overview](https://learn.adafruit.com/rgb-matrix-panels-with-raspberry-pi-5/overview)
- [Adafruit RGB Matrix Panels With Raspberry Pi 5 initialization config](https://learn.adafruit.com/rgb-matrix-panels-with-raspberry-pi-5/initialization-config)
- [Adafruit_Blinka_Raspberry_Pi5_Piomatter repository](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter)
- [Adafruit RGB LED Matrix Basics](https://learn.adafruit.com/32x16-32x32-rgb-led-matrix?view=all)
- [Raspberry Pi RP1 I/O controller documentation](https://www.raspberrypi.com/documentation/computers/io-controllers.html)

## Problem

- The current LED matrix path in `src/heart/device/rgb_display/device.py` imports `RGBMatrix` and `RGBMatrixOptions` directly from the `rgbmatrix` Python package and passes a narrow, hard-coded set of options into that library.
- The project needs a clean-room replacement implemented in Rust, with a small public configuration surface and a backend architecture that works on both Raspberry Pi 4 and Raspberry Pi 5.
- The implementation must not link against or wrap `hzeller/rpi-rgb-led-matrix`, and it must not inherit that library's option model as the public API.
- The implementation should preserve the current Heart runtime behavior where possible, but it should reduce the exposed option count to only the options the runtime actually uses today.
- Non-goals for this version:
  - Compatibility with the full `rgbmatrix` CLI or Python API.
  - Support for exotic multiplexed or PWM-only panels.
  - Support for all historical GPIO mappings.
  - Runtime-configurable panel mappers, privilege-drop options, or debug refresh counters.

## Design

### Architecture Overview

- Introduce a Rust-owned HUB75 runtime with a single public package surface exposed to Python through the existing `heart_rust` pattern.
- Keep the Python side narrow:
  - create a `MatrixConfig`
  - create a `MatrixDriver`
  - submit RGBA frames
  - close the driver
- Move all panel scan timing, bitplane generation, row scheduling, latch timing, blanking, and hardware-specific output into Rust.
- Replace the Python `MatrixDisplayWorker` with a Rust-owned render worker so Heart no longer depends on canvas-like methods such as `CreateFrameCanvas()` or `SwapOnVSync()`.

### Current Runtime Contract

- The runtime path in `src/heart/device/rgb_display/device.py` uses these inputs:
  - `panel_rows = Configuration.panel_rows()`
  - `panel_cols = Configuration.panel_columns()`
  - `chain_length = orientation.layout.columns`
  - `parallel = orientation.layout.rows`
- The runtime hard-codes these values:
  - `pwm_bits = 11`
  - `brightness = 100`
  - `pwm_lsb_nanoseconds = 100`
  - `gpio_slowdown = 4`
  - `led_rgb_sequence = "RGB"`
- The runtime also sets a group of legacy values that do not vary in Heart:
  - `show_refresh_rate = 1`
  - `disable_hardware_pulsing = False`
  - `multiplexing = 0`
  - `row_address_type = 0`
  - `pixel_mapper_config = ""`
  - `panel_type = ""`
  - `drop_privileges = False`
- This PRD intentionally removes the legacy group from the public API and treats their behavior as backend implementation details.

### Assumptions

- The first working version targets standard non-PWM HUB75 panels in common sizes:
  - `32x16`
  - `32x32`
  - `64x32`
  - `64x64`
- The first working version supports the Adafruit bonnet/HAT wiring profile first.
- The public config preserves `parallel` because the current Heart code sets it, but the implementation may support only a subset per backend in v1.
- The first Pi 5 implementation will use a deterministic RP1-backed engine rather than a userspace GPIO loop.

### Public API

The public API should expose one reduced configuration object and one runtime object.

```rust
pub enum WiringProfile {
    AdafruitHatPwm,
    AdafruitHat,
    AdafruitTripleHat,
}

pub enum ColorOrder {
    RGB,
    GBR,
}

pub struct MatrixConfig {
    pub wiring: WiringProfile,
    pub panel_rows: u16,
    pub panel_cols: u16,
    pub chain_length: u16,
    pub parallel: u8,
    pub color_order: ColorOrder,
}

pub struct MatrixStats {
    pub width: u32,
    pub height: u32,
    pub dropped_frames: u64,
    pub rendered_frames: u64,
    pub refresh_hz_estimate: f32,
    pub backend_name: String,
}

pub trait MatrixDriver {
    fn width(&self) -> u32;
    fn height(&self) -> u32;
    fn submit_rgba(&self, data: &[u8], width: u32, height: u32) -> Result<(), MatrixError>;
    fn clear(&self) -> Result<(), MatrixError>;
    fn stats(&self) -> MatrixStats;
    fn close(&self) -> Result<(), MatrixError>;
}
```

Python-facing package surface:

```python
class MatrixConfig:
    wiring: WiringProfile
    panel_rows: int
    panel_cols: int
    chain_length: int
    parallel: int
    color_order: ColorOrder

class MatrixDriver:
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def submit_rgba(self, data: bytes, width: int, height: int) -> None: ...
    def clear(self) -> None: ...
    def stats(self) -> MatrixStats: ...
    def close(self) -> None: ...
```

### Public Option Semantics

- `wiring`
  - Identifies the concrete GPIO layout and hardware assumptions.
  - `AdafruitHatPwm` is the primary v1 path.
  - `AdafruitHat` is optional for bring-up and debugging.
  - `AdafruitTripleHat` is allowed in the API but can return unsupported on Pi 5 in v1 if needed.
- `panel_rows`
  - Physical panel height in pixels.
  - Determines row-address depth:
    - `16` rows -> `3` address lines
    - `32` rows -> `4` address lines
    - `64` rows -> `5` address lines
- `panel_cols`
  - Physical panel width in pixels, usually `32` or `64`.
- `chain_length`
  - Number of panels daisy-chained along the shift-register path for one output port.
- `parallel`
  - Number of physical output ports driven at once.
  - This is retained from current Heart usage.
  - Expected support in v1:
    - Pi 4: `1..3`, depending on wiring profile
    - Pi 5: `1` required for the initial implementation
- `color_order`
  - Software channel remap before bitplane packing.
  - `GBR` exists because some publicly documented panels swap green and blue channels.

### Removed Public Options

The following current-library concepts should not be part of the new public API:

- `show_refresh_rate`
- `disable_hardware_pulsing`
- `multiplexing`
- `row_address_type`
- `pixel_mapper_config`
- `panel_type`
- `drop_privileges`
- `gpio_slowdown`
- `pwm_bits`
- `brightness`
- `pwm_lsb_nanoseconds`

These values should exist as internal backend defaults in v1:

- `pwm_bits = 11`
- `brightness_percent = 100`
- `lsb_dwell_ns = 100`
- `clock_slowdown_cycles = backend-tuned`

### Wiring Profiles

#### AdafruitHatPwm

This is the preferred v1 wiring profile for Raspberry Pi 4 and the primary reference profile for the bonnet form factor.

From the public Adafruit bonnet guide:

- Color lines:
  - `R1 = GPIO5`
  - `G1 = GPIO13`
  - `B1 = GPIO6`
  - `R2 = GPIO12`
  - `G2 = GPIO16`
  - `B2 = GPIO23`
- Control lines:
  - `CLK = GPIO17`
  - `LAT = GPIO21`
  - `OE net = GPIO4`
- Address lines:
  - `A = GPIO22`
  - `B = GPIO26`
  - `C = GPIO27`
  - `D = GPIO20`
  - `E = GPIO24`
- `AdafruitHatPwm` adds a hardware bridge from `GPIO18` to the bonnet's `OE` signal path so hardware-timed blanking can drive the OE net.

Implementation rule:

- `AdafruitHatPwm` must fail at startup if the selected backend cannot provide a hardware-timed OE output.

#### AdafruitHat

- Same signal map as `AdafruitHatPwm`, but OE is driven directly without the `GPIO18` bridge.
- This exists for development and fallback only.
- It is not the preferred production wiring profile because timing quality is worse.

#### AdafruitTripleHat

From the public Adafruit triple bonnet guide:

- Shared control:
  - `OE = GPIO18`
  - `CLK = GPIO17`
  - `LAT = GPIO4`
- Shared address:
  - `A = GPIO22`
  - `B = GPIO23`
  - `C = GPIO24`
  - `D = GPIO25`
  - `E = GPIO15`
- Port 1 RGB:
  - `R1 = GPIO11`
  - `G1 = GPIO27`
  - `B1 = GPIO7`
  - `R2 = GPIO8`
  - `G2 = GPIO9`
  - `B2 = GPIO10`
- Port 2 RGB:
  - `R1 = GPIO12`
  - `G1 = GPIO5`
  - `B1 = GPIO6`
  - `R2 = GPIO19`
  - `G2 = GPIO13`
  - `B2 = GPIO20`
- Port 3 RGB:
  - `R1 = GPIO14`
  - `G1 = GPIO2`
  - `B1 = GPIO3`
  - `R2 = GPIO26`
  - `G2 = GPIO16`
  - `B2 = GPIO21`

Implementation rule:

- Pi 4 may support `AdafruitTripleHat` in v1 if engineering time allows.
- Pi 5 support for `AdafruitTripleHat` is explicitly optional in v1 and may return unsupported.

### Frame Pipeline

#### Input Contract

- Heart produces a `pygame.Surface` in Python.
- `src/heart/device/rgb_display/device.py` already converts that surface into bytes with `pygame.image.tostring(screen, RGBA_IMAGE_FORMAT)`.
- The new driver must accept raw `RGBA8888` bytes directly.
- `width` and `height` passed into `submit_rgba()` must equal:
  - `panel_cols * chain_length`
  - `panel_rows * parallel`

#### Buffering Contract

- The Rust side owns the display worker thread or task.
- The driver keeps a queue depth of `2`.
- On overflow:
  - discard the oldest queued frame
  - keep the latest submitted frame
- This matches the current Python `MatrixDisplayWorker` behavior in `src/heart/device/rgb_display/worker.py`.

#### Internal Representation

- Store the latest user frame as packed `RGBA8888` or convert immediately to planar `RGB888`.
- Convert to bitplanes before scanout.
- The internal scan representation should be:
  - grouped by row address
  - grouped by bitplane
  - grouped by output port if `parallel > 1`

### HUB75 Scan Specification

The runtime must implement a standard direct-address HUB75 row-pair scan engine.

Signal model from public HUB75 docs:

- `R1/G1/B1` carry one pixel column for the top half of the active row pair.
- `R2/G2/B2` carry one pixel column for the bottom half of the active row pair.
- `A/B/C/D/E` select which row pair is active.
- `CLK` shifts the next RGB column into the panel chain.
- `LAT` latches the shifted row data.
- `OE` blanks the panel during data and address transitions and enables light during row dwell.

For each frame:

1. Convert the source frame into bitplanes for `11` PWM bits.
1. For each bitplane from least to most significant:
1. For each row address group:
1. Blank the panel by deasserting output.
1. Set `A..E` for the target row group.
1. Shift `panel_cols * chain_length` clock cycles worth of color data into each active output port.
1. Pulse `LAT`.
1. Enable output for the plane dwell time.
1. Repeat forever with the latest available frame.

Plane dwell time formula:

- `dwell_ns(bit) = lsb_dwell_ns * (1 << bit)`
- In v1 use `lsb_dwell_ns = 100`
- In v1 use full brightness, so no additional brightness scaling is required

### Backend Design

Both backends share the same high-level structure:

- `MatrixCore`
  - validates config
  - computes dimensions
  - accepts `submit_rgba()`
  - owns statistics
- `BitplanePacker`
  - converts `RGBA8888` into row/bitplane scan data
  - applies `color_order`
- `ScanScheduler`
  - computes row order and dwell schedule
- backend-specific `SignalEngine`
  - turns packed scan data into deterministic pin transitions

#### Pi4Backend

Target:

- Raspberry Pi 4 only.

Hardware model:

- Drive GPIO from a deterministic DMA-backed or equivalent hardware-paced engine.
- Do not implement scanout as a normal thread that toggles GPIO in userspace.
- Hardware-timed output is required because HUB75 blanking and latch windows are timing-sensitive.

Required behavior:

- Support `AdafruitHatPwm` first.
- Support `parallel = 1` as the minimum working version.
- Supporting `parallel = 2` or `3` is allowed if the chosen engine can present multiple RGB buses at once.

Implementation details:

- Precompute one scan buffer per frame in RAM.
- Each scan buffer entry should encode:
  - RGB output bits for the active port set
  - address bits `A..E`
  - `CLK`
  - `LAT`
  - `OE`
- The signal engine streams the scan buffer with deterministic timing.
- `OE` blanking must be hardware-timed, not software-slept.

Acceptance criteria:

- A single 64x32 panel on `AdafruitHatPwm` displays a stable image for at least 30 minutes.
- No visible tearing when submitting new frames at 30 FPS.
- No sustained ghosting on a test pattern with full-red, full-green, full-blue, and checkerboard rows.

#### Pi5Backend

Target:

- Raspberry Pi 5 only.

Hardware model:

- Use RP1-backed deterministic I/O.
- Prefer an RP1 PIO-style engine or another RP1-owned hardware-timed output path.
- Raspberry Pi documents RP1 as the I/O controller responsible for GPIO/PWM class peripherals on Pi 5.
- Public Pi 5 matrix guidance from Adafruit explicitly states older Pi approaches do not work and uses a PIO-based path.
- Use `Adafruit_Blinka_Raspberry_Pi5_Piomatter` as the primary public reference for Pi 5 bring-up assumptions, resource ownership, and the general shape of a Pi 5 HUB75 runtime.

What "RP1 PIO-based engine" means for this project:

- The runtime prepares scan words in memory.
- An RP1-owned hardware execution engine emits GPIO transitions with deterministic timing.
- The engine, not a Rust thread, owns sub-microsecond `CLK`, `LAT`, `OE`, and row-address timing.

Required behavior:

- Support `AdafruitHatPwm` first.
- Support `parallel = 1` in v1.
- Support chained multi-panel width through `chain_length`.

Implementation details:

- Build the same `BitplanePacker` and `ScanScheduler` used by `Pi4Backend`.
- Swap only the `SignalEngine`.
- The backend must use a kernel or device interface that gives deterministic RP1 timing control rather than raw userspace GPIO bit-banging.
- The backend must reserve or validate ownership of the selected GPIO pins before scan start.
- Treat `Adafruit_Blinka_Raspberry_Pi5_Piomatter` as a reference for:
  - requiring `/dev/pio0` or equivalent Pi 5 PIO device access
  - validating that the running firmware and kernel expose Pi 5 PIO support
  - documenting the need for non-root group access when device permissions default to `root:root`
  - structuring the Pi 5 signal engine around a hardware-managed PIO program instead of a CPU-timed GPIO loop
- Do not copy Piomatter code, APIs, or internal constants directly into Heart. Use it as a behavioral and systems-integration reference only.

Acceptance criteria:

- A single 64x32 panel on the Adafruit bonnet displays a stable image on Raspberry Pi 5.
- Measured `CLK`, `LAT`, and `OE` timing is stable across frame updates.
- Frame submission from Python does not stall the scan loop.

### Error Model

Driver creation must fail with explicit errors for:

- unsupported Pi model for the selected backend
- unsupported `parallel` count for the selected backend
- unsupported `panel_rows`
- unsupported `wiring` profile
- missing hardware-timed OE support for `AdafruitHatPwm`
- mismatched frame size in `submit_rgba()`
- inability to reserve hardware resources

### Pi 5 `/dev/pio0` Decisions

- `Pi5Backend` v1 requires `/dev/pio0`.
- Startup must treat `/dev/pio0` as a hard dependency rather than an optional acceleration path.
- If `/dev/pio0` is missing:
  - fail driver initialization
  - report that the system is not ready for the Pi 5 backend
  - tell the operator to update Pi 5 firmware and kernel until PIO device support is present
- If `/dev/pio0` exists but is not readable and writable by the current process:
  - fail driver initialization
  - report the current owner, group, and mode if they can be queried
  - recommend the udev rule documented by Adafruit and Piomatter:
    - `SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"`
  - recommend ensuring the runtime user is in the `gpio` group
  - recommend reboot or re-login after changing udev rules or group membership
- `Pi5Backend` must not attempt privilege escalation or `sudo` fallback internally.
- `Pi5Backend` should run this readiness check before allocating frame buffers or starting the scan thread.

Required startup checks for `Pi5Backend`:

1. Confirm the machine is a Raspberry Pi 5.
1. Confirm `/dev/pio0` exists.
1. Confirm `/dev/pio0` is accessible for the current user.
1. Confirm the selected wiring profile is supported by the Pi 5 backend.
1. Confirm the requested geometry can be represented by the selected pinout and row-address depth.

Reference commands for engineering bring-up:

- `ls -l /dev/pio0`
- `id`
- `uname -a`
- `sudo rpi-update`
- `sudo apt update && sudo apt upgrade`

Reference interpretation:

- Missing `/dev/pio0` means the system software stack is too old or not exposing Pi 5 PIO support.
- `/dev/pio0` owned by `root:root` with restrictive permissions means the driver will need either root or the documented udev/group fix.
- Presence and access to `/dev/pio0` should be considered necessary but not sufficient; the backend still needs successful pin and timing-engine initialization.

Pin and resource ownership decisions:

- While `Pi5Backend` is active, all pins in the selected wiring profile are reserved exclusively for HUB75 output.
- No other process or subsystem should be allowed to reuse those pins during driver lifetime.
- The backend should claim exclusive access through the Pi 5 PIO/device API if that API supports explicit reservation.
- If explicit reservation is not available, the backend should still:
  - validate that the requested pin set matches the chosen wiring profile
  - document those pins as unavailable for concurrent use
  - fail fast on any initialization error that suggests pin or device contention

Bring-up scope decisions for v1:

- `Pi5Backend` v1 will target the single Adafruit bonnet/HAT path first.
- `AdafruitHatPwm` on one logical lane is the required bring-up target.
- Multi-panel width via `chain_length` is in scope.
- Triple-bonnet or other multi-lane Pi 5 output is out of scope for the first working version unless the engineering path is straightforward after single-lane bring-up.

Piomatter reference decisions:

- Use Piomatter's public setup guidance as the reference for system prerequisites:
  - Pi 5 only
  - recent firmware and kernel
  - `/dev/pio0` present
  - udev access configured for non-root users
- Use Piomatter's public geometry model as a reference for Pi 5 configuration translation:
  - total `width`
  - total `height`
  - `n_addr_lines`
  - optional mapping for multi-lane configurations
- Do not copy Piomatter code, constants, or internal APIs.
- Treat Piomatter as a behavioral reference for:
  - expected system setup
  - one-panel bring-up
  - multiple-panel geometry concepts
  - Pi 5-specific execution model

### Integration With Heart

Python integration changes:

- `src/heart/device/rgb_display/device.py`
  - replace `from rgbmatrix import RGBMatrix, RGBMatrixOptions`
  - create `heart_rust.MatrixConfig`
  - create `heart_rust.MatrixDriver`
  - pass `pygame.image.tostring()` bytes directly into `submit_rgba()`
- `src/heart/device/rgb_display/worker.py`
  - remove from the production path once the Rust worker is ready
- `src/heart/device/selection.py`
  - keep the existing Pi detection and warning behavior, but switch to selecting the Rust driver

Expected config translation:

```python
config = MatrixConfig(
    wiring=WiringProfile.AdafruitHatPwm,
    panel_rows=Configuration.panel_rows(),
    panel_cols=Configuration.panel_columns(),
    chain_length=orientation.layout.columns,
    parallel=orientation.layout.rows,
    color_order=ColorOrder.RGB,
)
```

### Observability

- `stats()` must return:
  - rendered frame count
  - dropped frame count
  - active backend name
  - logical width and height
  - refresh rate estimate
- Rust should log initialization failures and unsupported configs with enough detail to diagnose panel and wiring issues.

### Validation Plan

Functional validation:

- bring-up pattern:
  - solid red
  - solid green
  - solid blue
  - white
  - checkerboard
  - row address walk
- verify `RGB` and `GBR` color-order modes
- verify single-panel and chained-panel width

Electrical validation:

- capture `CLK`, `LAT`, `OE`, and one RGB data line on a logic analyzer or scope
- verify that:
  - `OE` is blank during shift and latch
  - `LAT` pulses once per row load
  - `CLK` period is stable
  - address lines settle before OE enable

Performance validation:

- hold 30 FPS frame submissions for 30 minutes
- confirm that frame-dropping logic prefers freshness over queue growth
- verify that scanout continues if Python frame submissions pause

Safety validation:

- verify panel power is external 5V and not sourced from GPIO
- verify Pi 5 test setups use the official Pi USB-C supply in addition to matrix power

### Trade-Offs And Alternatives Considered

- Mirroring `RGBMatrixOptions` was rejected because it preserves upstream abstraction debt and exposes many options Heart does not use.
- A pure userspace GPIO bit-bang loop was rejected because timing stability is not good enough for reliable HUB75 output, especially on Pi 5.
- A separate daemon process was considered, but this version keeps the runtime inside the Rust extension package because the primary goal here is a clean-room driver and a reduced API, not a GPL boundary workaround.
- Supporting every historical mapping was rejected in favor of starting with one known-good wiring profile.

## Open Questions

- Does the current Heart deployment require `parallel > 1` in practice, or is `parallel = 1` sufficient for the first release?
- Should `AdafruitTripleHat` ship in the first version, or should it wait until the single-output path is stable on both Pi 4 and Pi 5?
- Should brightness remain fixed at `100` in v1, or should a single `brightness_percent` escape hatch be added before release?
- Validation tasks:
  - confirm exact OE timing requirements on the target panels used by Heart
  - confirm whether any currently deployed panels need `GBR` color order
  - confirm whether Heart uses 64-row panels that require the `E` address line today

## Future Ideas

- Add a single optional `MatrixTuning` struct once the default behavior is stable:
  - `brightness_percent`
  - `pwm_bits`
  - `lsb_dwell_ns`
- Add panel-layout mapping for serpentine or tiled arrangements once the base direct chain path is stable.
- Add `AdafruitTripleHat` on Pi 5 after the single-output RP1 engine is validated.
- Add a display simulator backend for desktop testing that consumes the same bitplane packing path without touching GPIO.
