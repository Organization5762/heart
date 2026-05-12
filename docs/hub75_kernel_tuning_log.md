# HUB75 Kernel Tuning Log

## 2026-05-12

### What changed

- Checkpoint commit: `c8462ef8` (`Add HUB75 logic scoring harness`)
- Added [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) to summarize raw Logic CSV exports and score candidate captures against a baseline on a normalized `0..1` scale.
- Added [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with focused synthetic timing regressions for extra clocks and address chatter while output is enabled.
- Added [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py) for ad hoc scoring against saved captures.
- Added [`docs/hub75_kernel_signal_baselines.json`](/Users/lampe/code/heart/docs/hub75_kernel_signal_baselines.json) to track the intended PIO baseline and the temporary bootstrap reference.

### Live kernel-path observations

- On `totem4`, `/dev/rp1-hub75` exists and the `rp1_hub75` module is loaded.
- Direct execution as `michael` failed with `Permission denied` because the device node is `0600 root:root`.
- Building `rp1_hub75_color_loop` as `michael` and running the resulting binary under `sudo` worked:
  - `submitted=1733`
  - `elapsed_s=3.000`
  - `submit_hz=577.64`
  - `frames_presented=1733`
  - `frames_dropped=0`
- This proves the current misc-device path is queueing and software-presenting frames cleanly, but it does not yet prove waveform similarity to the known-good PIO path.

### Baseline status

- I did not find a saved PIO logic capture in the local trees during this run.
- I did find many saved direct-RIO/Saleae captures in `/Users/lampe/code/linux`, which are enough to validate the scorer and keep the harness moving.
- The baseline manifest therefore records:
  - the required known-good PIO command as the real baseline target
  - a temporary direct-RIO capture as the bootstrap scoring reference

### Current blockers

- Local Saleae automation preflight via the historical script is not currently available in this session:
  - no `saleae` Python package in the selected interpreter
  - no Logic automation port reachable on `127.0.0.1:10430`
- Because of that, this run could not record the fresh PIO baseline capture the new scoring harness expects.

### Next experiments

1. Restore or replace local Logic automation so the new scorer can compare a fresh PIO capture against a fresh `rp1-hub75` capture.
2. Fix `/dev/rp1-hub75` access semantics for non-root runtime use, either with a device-mode policy or a userspace wrapper that is explicit and reproducible.
3. Once capture is live, run the red-only kernel submitter and the known-good PIO submitter through the same CSV scorer, then optimize the kernel path for `>=1000 Hz` without regressing control ordering or clock-shape similarity.

### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/linux/.rp1-runs/tool-selftest-stream/good/digital.csv /Users/lampe/code/linux/.rp1-runs/tool-selftest-stream/bad-clock/digital.csv`
