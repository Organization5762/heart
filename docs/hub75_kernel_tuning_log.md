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

## 2026-05-12 Follow-up

### What changed

- Tightened [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so row-dependent metrics are gated on actual row activity.
- Added a flatline regression to [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) so an electrically silent candidate scores near zero instead of looking partially healthy.

### Live kernel-path observations

- On `totem4`, building `rp1_hub75_color_loop` as `michael` and running it under `sudo` still submits frames successfully:
  - `submitted=3702`
  - `submit_hz=1850.74`
  - `frames_presented=3701`
  - `frames_dropped=0`
- While that loop is running, `pinctrl get 5,6,12,13,16,17,18,20,21,22,23,24,26,27` shows the HUB75 pins staying in `PIO*` mux mode instead of moving under a GPIO-driving path. This matches the driver documentation: the current `/dev/rp1-hub75` path is still a packer/queue only, not a scan engine.

### Logic capture status

- The `logic2` connector can see the Saleae hardware, but starting a fresh capture failed with `Cannot switch sessions while recording`.
- The legacy local Saleae Python path is still unavailable in this repo environment (`saleae` package missing, no local Logic app automation port), so this run could not yet record a fresh PIO baseline or a fresh kernel-path flatline capture.

### Interpretation

- The immediate blocker is no longer "module not loaded". The blocker is that the custom kernel route does not yet own or drive the HUB75 pins, so it cannot produce the electrical waveform we want to compare against the PIO baseline.
- The next practical implementation step is to connect a real RP1-side consumer to the `/dev/rp1-hub75` queue, or extend the driver so `RP1H_START_WORKER` can launch a real scan worker instead of only accepting external software-vsync heartbeats.

### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/linux/.rp1-runs/tool-selftest-stream/good/digital.csv /Users/lampe/code/linux/.rp1-runs/tool-selftest-stream/bad-clock/digital.csv`
- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && sudo ./target/debug/rp1_hub75_color_loop 2000 0'`
- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && rm -f /tmp/rp1h_loop.log && (sudo ./target/debug/rp1_hub75_color_loop 5000 0 >/tmp/rp1h_loop.log 2>&1 &) ; sleep 0.5; pinctrl get 5,6,12,13,16,17,18,20,21,22,23,24,26,27; wait; tail -n 20 /tmp/rp1h_loop.log'`

## 2026-05-12 Red-only device bring-up

### What changed

- Added a deterministic solid-color mode to [`rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs`](/Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs) via `HEART_RP1_HUB75_COLOR_LOOP_SOLID`.
- Recorded the active Logic2 blocker in [`AGENTS.md`](/Users/lampe/code/heart/AGENTS.md) so future runs do not waste time rediscovering the `Cannot switch sessions while recording` failure mode.

### Live kernel-path observations

- The custom module on `totem4` is loaded and `/dev/rp1-hub75` exists as `0600 root:root`.
- Running the red-only submitter under `sudo` with `HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1 HEART_RP1_HUB75_COLOR_LOOP_SOLID=red` succeeded:
  - `submitted=1897`
  - `submit_hz=1896.82`
  - `words_per_frame=2048`
  - `frames_presented=1896`
  - `frames_dropped=0`
- This is the first clean proof in this repo state that the misc-device path can be driven as a single-plane, fixed-red publication source suitable for a bridge worker.

### Current blockers

- Fresh Logic captures are still blocked by the local Logic2 session state. The connector returns `Cannot switch sessions while recording`, so no same-day PIO baseline or same-day kernel-path flatline capture could be exported in this run.
- The local sandbox for this automation can edit [`/Users/lampe/code/heart`](/Users/lampe/code/heart) but not [`/Users/lampe/code/linux`](/Users/lampe/code/linux), so the intended `/dev/rp1-hub75` -> shared-SRAM bridge could not be landed directly in the kernel selftest tree from this session.

### Next implementation step

1. Land a small `rp1_hub75_bridge_state32` helper in `tools/testing/selftests/drivers/rp1-pio` that:
   - opens `/dev/rp1-hub75`
   - validates queued `STATE32`
   - copies the pending slot's plane data into RP1 shared SRAM at `0xc000`
   - calls `RP1H_SIGNAL_VSYNC` after each copy
2. Run that bridge against the existing `state32-...` core1 worker while the red-only submitter queues frames through `/dev/rp1-hub75`.
3. Once Logic2 capture is unblocked, score that bridged waveform against the known-good PIO baseline with the existing scorer.

### Validation

- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `scp /Users/lampe/code/heart/rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs michael@totem4.local:/home/michael/heart/rust/heart_rgb_matrix_driver/src/bin/rp1_hub75_color_loop.rs`
- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && sudo env HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1 HEART_RP1_HUB75_COLOR_LOOP_SOLID=red ./target/debug/rp1_hub75_color_loop 1000 0'`

## 2026-05-12 Queue-to-SRAM bridge bring-up

### What changed

- Added [`scripts/rp1_hub75_bridge_state32.c`](/Users/lampe/code/heart/scripts/rp1_hub75_bridge_state32.c), a standalone userspace bridge for the current bring-up path.
- The bridge opens `/dev/rp1-hub75`, mmaps the queued `STATE32` slots, copies the pending slot into RP1 shared SRAM at `0xc000`, and issues `RP1H_SIGNAL_VSYNC` so the kernel worker state remains externally heartbeated.
- Because this session cannot write [`/Users/lampe/code/linux`](/Users/lampe/code/linux), the helper was compiled and exercised on `totem4` from `/home/michael/rp1-pio` as a deployment mirror of the local source.

### Live kernel-path observations

- The no-PIO worker candidate
  `state32-dsramcache-copy11plane-clkout-addrsetupnop8-seedoe-copydelay5-splithead1-allslow-lat2-clknop-regcount-dwell1`
  stayed stable while the bridge drove it from `/dev/rp1-hub75` traffic:
  - remote worker counter: `aggregate_fps=2521.580`
  - red-only submitter: `submitted=13419`, `submit_hz=1916.86`
  - bridge: `copies=10842`, `bytes_per_frame=8192`
- That is the first proof in this repo state that the custom kernel queue can feed the existing no-PIO scan worker with a real pending-slot consumer instead of only software-presenting stats.
- The current bridge path is intentionally one-plane (`HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1`) so the copied payload fits the existing `0xc000` shared-SRAM publication window used by the direct worker bring-up.

### Logic capture status

- The Logic2 connector is now reachable and can start/stop captures, so the earlier `Cannot switch sessions while recording` blocker is no longer the active failure mode for this session.
- However, fresh exports from channels `0..6` and a discovery pass across channels `0..15` still came back electrically flat while the known-good PIO probe was active.
- The all-channel discovery capture showed only static levels on channels `9` and `11`, with no observed edges anywhere else in the exported CSV, so the current blocker has shifted from "Logic session stuck" to "probe/channel mapping or fixture routing does not match the assumed HUB75 channel map".
- Because of that instrumentation issue, this run could not produce a trustworthy same-day live similarity score between the PIO path and the bridged kernel path, even though the bridge itself is functioning.

### Next implementation directions

1. Fix the Saleae probe/channel mapping before treating any new live similarity score as meaningful. The quickest next move is a deliberate channel-identification pass, not more waveform tuning.
2. Once capture is trustworthy, record a one-plane PIO baseline and a one-plane bridged-kernel capture under the same threshold/channel map, then score those with the existing `0..1` harness.
3. If the live one-plane waveform is clean, move the bridge boundary inward:
   either expose the pending slot more explicitly in the UAPI header or land an RP1-side/in-kernel consumer so the queue no longer depends on a polling userspace copier.
4. After the one-plane bridge is electrically proven, revisit higher PWM publication, because the current `0xc000` publication workaround is only sized for the one-plane bring-up shape.

### Validation

- `ssh michael@totem4.local 'cd /home/michael/heart/rust/heart_rgb_matrix_driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `scp /Users/lampe/code/heart/scripts/rp1_hub75_bridge_state32.c michael@totem4.local:/home/michael/rp1-pio/rp1_hub75_bridge_state32.c`
- `ssh michael@totem4.local 'cd /home/michael/rp1-pio && gcc -O2 -Wall -Wextra -o rp1_hub75_bridge_state32 rp1_hub75_bridge_state32.c'`
- `ssh michael@totem4.local 'set -eu; cd /home/michael/rp1-pio; rm -f /tmp/rp1h_candidate.log /tmp/rp1h_submitter.log /tmp/rp1h_bridge.log; ( RP1_HUB75_SEED_SOLID=red ./rp1_hub75_run_candidate.sh state32-dsramcache-copy11plane-clkout-addrsetupnop8-seedoe-copydelay5-splithead1-allslow-lat2-clknop-regcount-dwell1 8 >/tmp/rp1h_candidate.log 2>&1 ) & candidate_pid=$!; sleep 0.8; ( cd /home/michael/heart/rust/heart_rgb_matrix_driver && sudo -n env HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1 HEART_RP1_HUB75_COLOR_LOOP_SOLID=red HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE=0 ./target/debug/rp1_hub75_color_loop 5000 0 >/tmp/rp1h_submitter.log 2>&1 ) & submitter_pid=$!; sleep 0.8; ( cd /home/michael/rp1-pio && sudo -n ./rp1_hub75_bridge_state32 5 /dev/rp1-hub75 0xc000 1 >/tmp/rp1h_bridge.log 2>&1 ) & bridge_pid=$!; wait $bridge_pid; wait $submitter_pid || true; wait $candidate_pid || true; tail -n 20 /tmp/rp1h_candidate.log; tail -n 20 /tmp/rp1h_submitter.log; tail -n 20 /tmp/rp1h_bridge.log'`
- `ssh michael@totem4.local 'printf \"%s\\n\" \"candidate\"; tail -n 30 /tmp/rp1h_candidate.log; printf \"%s\\n\" \"submitter\"; tail -n 30 /tmp/rp1h_submitter.log; printf \"%s\\n\" \"bridge\"; tail -n 30 /tmp/rp1h_bridge.log'`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/heart/.captures/20260512-pio-baseline/digital.csv /Users/lampe/code/heart/.captures/20260512-rp1h-bridge/digital.csv`
