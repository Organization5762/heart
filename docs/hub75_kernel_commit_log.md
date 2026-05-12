# HUB75 Kernel Commit Log

## 2026-05-12

- `c8462ef8` `Add HUB75 logic scoring harness`
  - Added the repo-local Hub75 CSV scorer, synthetic regression tests, baseline manifest, and this tuning log scaffold.
- `8e0ab946` `Tighten HUB75 silent-waveform scoring`
  - Gates row-dependent similarity metrics on actual row activity and adds a flatline regression so a non-driving kernel path scores near zero.
- `working tree` `Add red-only HUB75 submitter mode`
  - [`rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs) now accepts `HEART_RP1_HUB75_COLOR_LOOP_SOLID` so the misc-device queue can be driven as a deterministic fixed-red source during bridge bring-up.
