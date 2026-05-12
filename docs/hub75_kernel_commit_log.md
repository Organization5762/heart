# HUB75 Kernel Commit Log

## 2026-05-12

- `a034299a` `Fail fast on transport-only rp1-hub75 path`
  - Changed [`rust/heart_rgb_matrix_driver/src/runtime/rp1_hub75.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/runtime/rp1_hub75.rs) so software-vsync is opt-in instead of default, and the backend now errors once frames queue without any present/vsync progress from a real worker.
  - Added the matching tuning knob in [`rust/heart_rgb_matrix_driver/src/runtime/tuning.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/runtime/tuning.rs) and documented the behavior in [`rust/heart_rgb_matrix_driver/README.md`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/README.md).
- `12c632a8` `Add RP1 HUB75 bridge bring-up helper`
  - Added [`scripts/rp1_hub75_bridge_state32.c`](/Users/lampe/code/heart/scripts/rp1_hub75_bridge_state32.c) as a standalone userspace bridge that consumes queued `STATE32` slots from `/dev/rp1-hub75`, copies the pending slot into RP1 shared SRAM, and heartbeats presentation with `RP1H_SIGNAL_VSYNC`.
  - Updated [`docs/hub75_kernel_tuning_log.md`](/Users/lampe/code/heart/docs/hub75_kernel_tuning_log.md) with the live bridge results and the current Logic2 probe-mapping blocker.
- `c8462ef8` `Add HUB75 logic scoring harness`
  - Added the repo-local Hub75 CSV scorer, synthetic regression tests, baseline manifest, and this tuning log scaffold.
- `8e0ab946` `Tighten HUB75 silent-waveform scoring`
  - Gates row-dependent similarity metrics on actual row activity and adds a flatline regression so a non-driving kernel path scores near zero.
- `220cd53d` `Add red-only HUB75 submitter mode`
  - [`rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs) now accepts `HEART_RP1_HUB75_COLOR_LOOP_SOLID` so the misc-device queue can be driven as a deterministic fixed-red source during bridge bring-up.
