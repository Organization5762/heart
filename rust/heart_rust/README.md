# Heart Rust Runtime

`heart_rust` is the native display/runtime package used by the Python `heart`
application. It provides two related pieces:

- a PyO3 extension that exposes the matrix driver and scene-management bridge
  to Python
- a Pi 5 resident-scan kernel module that keeps packed HUB75 scan data resident
  in kernel memory and replays it efficiently

The package is small at the Python API boundary, but it owns the
performance-sensitive display path on Raspberry Pi hardware.

## What Lives Here

### Python-facing extension

The Rust crate builds the private `_heart_rust` extension module and the Python
shim package under [`python/heart_rust`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/python/heart_rust).
That surface is intentionally close to the existing Python matrix API:

- `NativeMatrixDriver` accepts RGBA frames from Python
- `MatrixDriverCore` runs the backend worker and queueing logic in Rust
- `SceneManagerBridge` and `SceneSnapshot` keep scene-selection state in Rust
- the Python wrapper exposes compatibility helpers such as
  `CreateFrameCanvas()` and `SwapOnVSync()`

### Pi 5 scan runtime

The Pi 5 path is implemented in
[`src/runtime/pi5_scan.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/runtime/pi5_scan.rs)
plus two C transport layers:

- [`native/pi5_pio_scan_shim.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/native/pi5_pio_scan_shim.c):
  raw userspace `rp1-pio` transport
- [`kernel/pi5_scan_loop/heart_pi5_scan_loop.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/kernel/pi5_scan_loop/heart_pi5_scan_loop.c):
  resident-loop kernel module

Rust packs RGBA input into a compact scan stream. The transport layer then
feeds that stream to RP1 PIO. On Pi 5, the kernel resident loop is the fast
path because it can keep one packed frame resident and replay it without
repacking in userspace.

## High-Level Data Flow

1. Python renders an RGBA image.
1. `NativeMatrixDriver.submit_rgba()` hands that frame to Rust.
1. The Rust runtime reorders color channels if needed and reuses pooled frame
   buffers to avoid per-frame allocation churn.
1. On Pi 5, Rust packs RGBA into a compact row-pair/bitplane scan stream.
1. The kernel resident-loop module loads that packed frame once and replays it
   until a newer frame arrives.

Two details matter for performance:

- the Pi 5 backend owns steady-state refresh in hardware, so the generic Rust
  runtime worker should not re-submit unchanged frames in software
- the packed scan format tries to reduce replay bytes aggressively through
  blank-group omission, blank-span trimming/splitting, identical-plane merging,
  and dense GPIO-word packing

## Kernel Module

The Pi 5 kernel module is an out-of-tree module in
[`kernel/pi5_scan_loop`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/kernel/pi5_scan_loop).
It exists because the userspace `rp1-pio` interface is good enough for one-shot
submission, but not ideal for a resident self-refreshing display loop.

The module exposes a small control surface:

- `INIT`: allocate resident storage and configure the PIO parser
- `LOAD`: copy one fully packed frame into resident storage
- `START`: begin resident replay
- `WAIT` / `STATS`: report completed presentations
- `STOP`: stop replay

Two semantics matter when maintaining this path:

- `LOAD` replaces the resident replay payload; it is not a partial-update API.
- `WAIT` / `STATS` report kernel-owned transport completion counts, not an
  inferred userspace refresh estimate.

DKMS packaging for the module lives in
[`kernel/pi5_scan_loop/dkms.conf`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/kernel/pi5_scan_loop/dkms.conf),
and the Pi installer script that stages and registers it lives in
[`packages/heart-device-manager/src/heart_device_manager/install_pi5_scan_loop_dkms.sh`](/Users/lampe/.codex/worktrees/b4c5/heart/packages/heart-device-manager/src/heart_device_manager/install_pi5_scan_loop_dkms.sh).

## Building

### Local development

- Install project dependencies with `uv`.
- Build the extension in place with `maturin develop --release`.
- Generate/update stubs with `cargo run --bin stub_gen`.

The maturin configuration is pinned to a release build in
[`pyproject.toml`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/pyproject.toml),
so packaged builds use optimized Rust code by default.

### Pi install path

Use the repository installer rather than trying to install the kernel module as
a plain `pip` side effect:

- `make pi_install`

That path installs the Python package, stages the DKMS source, builds the
kernel module against the current Pi kernel, registers it with DKMS, and loads
the module with the current replay tuning defaults.

## Runtime Tuning

Behavioral tuning knobs for the Rust runtime live in
[`src/runtime/tuning.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/runtime/tuning.rs)
and use `HEART_*` environment variables. These are read once and cached on
first use, so they should be set before the Python process imports or
initializes `heart_rust`.

### General runtime

- `HEART_MATRIX_SIMULATED_REFRESH_INTERVAL_MS`
  Default: `16`
  Controls the software refresh interval for the simulated backend used when
  the runtime is not on a supported Pi target.

- `HEART_MATRIX_PI4_REFRESH_INTERVAL_MS`
  Default: `16`
  Controls the software refresh interval for the current placeholder Pi 4
  backend.

- `HEART_MATRIX_MAX_PENDING_FRAMES`
  Default: `2`
  Sets the maximum queued frames waiting behind the active frame before the
  oldest pending frame is dropped.

- `HEART_PARALLEL_COLOR_REMAP_THRESHOLD_BYTES`
  Default: `16384`
  RGBA buffers at or above this size use Rayon for `gbr` channel remapping;
  smaller buffers use the single-threaded path.

### Pi 5 scan packer and userspace transport

- `HEART_PI5_SCAN_DEFAULT_PWM_BITS`
  Default: `11`
  Default PWM bit depth used when constructing a Pi 5 scan config. Valid values
  are `1..=16`.

- `HEART_PI5_SCAN_PACK_PARALLEL_THRESHOLD_WORDS`
  Default: `8192`
  Packed scan jobs at or above this word count use Rayon to build row-pair /
  bitplane groups in parallel.

- `HEART_PI5_SCAN_INTERNAL_BLANK_RUN_MIN_PIXELS`
  Default: `5`
  Internal blank spans shorter than this stay inline; longer blank regions are
  emitted as explicit blank-span opcodes to reduce replay bytes.

- `HEART_PI5_SCAN_DEFAULT_DMA_BUFFER_COUNT`
  Default: `2`
  Buffer count used when configuring the raw userspace `rp1-pio` DMA transport.

- `HEART_PI5_SCAN_MAX_DMA_BUFFER_BYTES`
  Default: `22880`
  Upper bound for the raw userspace `rp1-pio` DMA buffer size. This only
  affects the raw transport, not the kernel resident-loop module.

- `HEART_PI5_SCAN_RESIDENT_LOOP_RESUBMIT_PAUSE_US`
  Default: `100`
  Pause between repeats of the same resident frame in the async userspace Pi 5
  transport. This is a transport fairness knob, not a kernel replay setting.

## Where To Read Next

- Packed scan format and layer split:
  [`docs/research/pi5_scan_transport_layers.md`](/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/pi5_scan_transport_layers.md)
- Rust runtime entrypoints:
  [`src/lib.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/lib.rs)
- Backend selection and worker behavior:
  [`src/runtime/backend.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/runtime/backend.rs),
  [`src/runtime/driver.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/runtime/driver.rs)
