# Heart RGB Matrix Driver Runtime

`heart_rgb_matrix_driver` is the native display/runtime package used by the Python `heart`
application. This crate owns the active runtime-facing matrix API, while the Piomatter work in
this repo is limited to parity, benchmark, and checkout-patching tooling.

It provides two related pieces:

- a PyO3 extension that exposes the matrix driver and scene-management bridge
  to Python
- a Pi 5 userspace scan transport that feeds RP1 PIO from a packed HUB75 stream

The package is small at the Python API boundary, but it owns the
performance-sensitive display path on Raspberry Pi hardware.

## What Lives Here

### Python-facing extension

The Rust crate builds the private `_heart_rgb_matrix_driver` extension module and the Python
shim package under [`python/heart_rgb_matrix_driver`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/python/heart_rgb_matrix_driver).
That surface is intentionally close to the existing Python matrix API:

- `NativeMatrixDriver` accepts RGBA frames from Python
- `MatrixDriverCore` runs the backend worker and queueing logic in Rust
- `SceneManagerBridge` and `SceneSnapshot` keep scene-selection state in Rust
- the Python wrapper exposes compatibility helpers such as
  `CreateFrameCanvas()` and `SwapOnVSync()`

### Pi 5 parity tooling

The Pi 5 path is implemented in
[`src/runtime/pi5_scan.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_scan.rs).

Rust packs RGBA input into a compact scan stream for simulator, audit, and parity
work. The runtime-facing Python path no longer links against the Piomatter adapter.

## High-Level Data Flow

1. Python renders an RGBA image.
1. `NativeMatrixDriver.submit_rgba()` hands that frame to Rust.
1. The Rust runtime reorders color channels if needed and reuses pooled frame
   buffers to avoid per-frame allocation churn.
1. Pi 5 parity tools can still pack RGBA into a compact row-pair/bitplane
   scan stream for audit and simulation work.

Two details matter for performance:

- the Pi 5 transport owns steady-state refresh in userspace, so the generic
  Rust runtime worker should not re-render unchanged frames in software
- the packed scan format tries to reduce replay bytes aggressively through
  blank-group omission, blank-span trimming/splitting, repeated-pin-word spans,
  identical-plane merging, and dense GPIO-word packing

## Building

### Local development

- Install project dependencies with `uv`.
- Build the extension in place with `maturin develop --release`.
- Generate/update stubs with `cargo run --bin stub_gen`.

The maturin configuration is pinned to a release build in
[`pyproject.toml`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pyproject.toml),
so packaged builds use optimized Rust code by default.

### Pi install path

Use the repository installer rather than trying to install the package as a
plain `pip` side effect:

- `make pi_install`

That path installs the Python package and the native userspace transport pieces
needed for runtime and parity bring-up.

## Runtime Tuning

Behavioral tuning knobs for the Rust runtime live in
[`src/runtime/tuning.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tuning.rs)
and use `HEART_*` environment variables. These are read once and cached on
first use, so they should be set before the Python process imports or
initializes `heart_rgb_matrix_driver`.

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

### Pi 5 scan packer and parity tooling

- `HEART_PI5_SCAN_DEFAULT_PWM_BITS`
  Default: `11`
  Default PWM bit depth used when constructing a Pi 5 scan config. Valid values
  are `1..=16`.

- `HEART_PI5_SCAN_PACK_PARALLEL_THRESHOLD_WORDS`
  Default: `8192`
  Packed scan jobs at or above this word count use Rayon to build row-pair /
  bitplane groups in parallel.

- `HEART_PI5_SCAN_MAX_DMA_BUFFER_BYTES`
  Default: `22880`
  Upper bound kept for parity experiments around packed Pi 5 transport sizing.

## Where To Read Next

- Packed scan format and layer split:
  [`docs/research/pi5_scan_transport_layers.md`](/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/pi5_scan_transport_layers.md)
- Rust runtime entrypoints:
  [`src/lib.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/lib.rs)
- Backend selection and worker behavior:
  [`src/runtime/backend.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/backend.rs),
  [`src/runtime/driver.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/driver.rs)
