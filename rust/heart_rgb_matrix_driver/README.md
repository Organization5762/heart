# Heart RGB Matrix Driver Runtime

`heart_rgb_matrix_driver` is the native display/runtime package used by the Python `heart`
application. This crate owns the active runtime-facing matrix API, while the Piomatter work in
this repo is limited to parity, benchmark, and checkout-patching tooling.

It provides two related pieces:

- a PyO3 extension that exposes the matrix driver and scene-management bridge
  to Python
- a Pi 5 backend that submits image frames to the patched kernel
  `/dev/rp1-hub75` misc-device packer

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

### Pi 5 kernel packer path

The runtime Pi 5 path is implemented in
[`src/runtime/rp1_hub75.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/runtime/rp1_hub75.rs).

For each submitted image, Rust converts the Python RGBA buffer into the kernel
UAPI's flat RGB888 layout and calls:

1. `open("/dev/rp1-hub75", O_RDWR | O_CLOEXEC)` during backend creation
1. `ioctl(fd, RP1H_CONFIG, &mut rp1h_config)` with `slot_count = 2` and
   `stream_format = RP1H_STREAM_STATE32`
1. `mmap(NULL, cfg.mmap_size, PROT_READ, MAP_SHARED, fd, 0)` to keep the
   queued packed stream visible to the display side
1. `ioctl(fd, RP1H_QUEUE_FRAME, &rp1h_queue_frame { length, data, .. })` for
   each submitted image, using `RP1H_QUEUE_F_REPLACE_PENDING` so animation
   updates replace any unpresented pending frame
1. optionally `ioctl(fd, RP1H_SIGNAL_VSYNC, &mut rp1h_vsync)` after queueing
   only when `HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE=1` is set for explicit
   software-vsync bring-up
1. optionally `ioctl(fd, RP1H_WAIT_PRESENT, &rp1h_wait_present)` when
   `HEART_RP1_HUB75_WAIT_PRESENT_TIMEOUT_NS` is set
1. optionally `ioctl(fd, RP1H_GET_PRESENT_STATS, &mut rp1h_present_stats)` when
   `HEART_RP1_HUB75_LOG_STATS` is set

Programmatic kernel packer counters are exposed through `RP1H_GET_STATS`, and
queued presentation counters are exposed through `RP1H_GET_PRESENT_STATS`.
Userspace can read both without constructing a display runtime:

- Rust: `heart_rgb_matrix_driver::rp1_hub75_read_pack_stats()`
- Rust: `heart_rgb_matrix_driver::rp1_hub75_read_present_stats()`
- Python: `heart_rgb_matrix_driver.rp1_hub75_get_stats()`
- Python: `heart_rgb_matrix_driver.rp1_hub75_get_present_stats()`
- CLI: `cargo run --bin rp1_hub75_stats -- /dev/rp1-hub75`

The display/worker side must call `RP1H_SIGNAL_VSYNC` at the safe frame
boundary. That promotes the pending queued slot to the displayed slot and wakes
optional `RP1H_WAIT_PRESENT` waiters. In the normal direct-RIO path this is
handled by the display/worker side; the Rust-side environment switch is for
software-vsync bring-up only and is disabled by default. The runtime now also
fails fast once frames are queued without any present/vsync progress so the
transport-only packer path cannot silently masquerade as a live display worker.

## High-Level Data Flow

1. Python renders an RGBA image.
1. `NativeMatrixDriver.submit_rgba()` hands that frame to Rust.
1. The Rust runtime drops alpha, optionally applies the configured channel
   order, and stores a flat row-major RGB888 frame.
1. On Pi 5, the backend submits that RGB888 frame to `/dev/rp1-hub75` with
   `RP1H_QUEUE_FRAME`.
1. The patched kernel packs the frame into the pending mmap slot as a STATE32
   stream for the RP1-side consumer, then `RP1H_SIGNAL_VSYNC` makes it visible
   at the next safe boundary.

Two details matter for performance:

- the kernel UAPI expects RGB888, not RGBA, so the native runtime keeps its
  queue buffers in the exact byte layout passed to `RP1H_QUEUE_FRAME`
- the local patched kernel currently accepts the double-buffered shape
  (`slot_count = 2`); wider queued rings remain kernel-side future work

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
