# HUB75 Kernel Commit Log

## 2026-05-12

- `c8462ef8` `Add HUB75 logic scoring harness`
  - Added the repo-local Hub75 CSV scorer, synthetic regression tests, baseline manifest, and this tuning log scaffold.
- `pending` `Tighten silent-waveform scoring`
  - Gates row-dependent similarity metrics on actual row activity and adds a flatline regression so a non-driving kernel path scores near zero.
