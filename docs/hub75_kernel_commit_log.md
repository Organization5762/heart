# HUB75 Kernel Commit Log

## 2026-05-12

## 2026-05-13

- `18c1e89d` `Diagnose static-rail HUB75 captures`

  - Extended [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so electrically silent captures now preserve per-channel initial/final levels, which exposes static-rail failures instead of reducing them to an empty flatline diagnosis.
  - Updated [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py) and [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) so the JSON payload and regression suite both cover the new static-level instrumentation path.
  - Recorded the same-day live PIO recapture, all-16 discovery recapture, and slow manual GPIO-toggle failure in [`docs/hub75_kernel_signal_baselines.json`](/Users/lampe/code/heart/docs/hub75_kernel_signal_baselines.json), [`docs/hub75_kernel_tuning_log.md`](/Users/lampe/code/heart/docs/hub75_kernel_tuning_log.md), and [`AGENTS.md`](/Users/lampe/code/heart/AGENTS.md), establishing that the current blocker is analyzer/probe routing rather than kernel waveform shape.

- `2d50adf4` `Diagnose silent HUB75 captures`

  - Added whole-capture diagnosis to [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so failed capture pairs now classify silent exports separately from channel-map mismatches and generic invalid HUB75 waveforms.
  - Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with explicit regressions for shifted live channels and globally silent captures.
  - Updated [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py), [`docs/hub75_kernel_signal_baselines.json`](/Users/lampe/code/heart/docs/hub75_kernel_signal_baselines.json), [`docs/hub75_kernel_tuning_log.md`](/Users/lampe/code/heart/docs/hub75_kernel_tuning_log.md), and [`AGENTS.md`](/Users/lampe/code/heart/AGENTS.md) to record that the current saved PIO and bridged-kernel CSVs are electrically silent across all captured channels, not just mis-mapped.

- `767f6254` `Reject flatline HUB75 baselines`

  - Tightened [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so dead Saleae exports are marked invalid and gated out of the similarity score.
  - Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with a flatline-vs-flatline regression so bogus `1.0` matches stay blocked.
  - Updated [`docs/hub75_kernel_tuning_log.md`](/Users/lampe/code/heart/docs/hub75_kernel_tuning_log.md) with the current Logic2 session blocker and validation results.

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
