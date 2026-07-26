# HUB75 Kernel Tuning Log

## 2026-05-12

### Live capture recheck: bench still flat, scorer now accepts explicit remaps

#### What changed

- Updated [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py) so the CLI now accepts repeated `--signal NAME=CHANNEL` overrides and includes the resolved signal map in its JSON payload.
- Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with a regression that proves a shifted live waveform becomes `valid_hub75` once the correct channel map is supplied.
- Recorded two fresh Logic2 MCP captures under [`/Users/lampe/code/heart/.captures/20260512-pio-baseline-live2-all16`](/Users/lampe/code/heart/.captures/20260512-pio-baseline-live2-all16) and [`/Users/lampe/code/heart/.captures/20260512-manual-toggle-live-all16`](/Users/lampe/code/heart/.captures/20260512-manual-toggle-live-all16).

#### Live observations

- `totem4` still reports the custom module loaded and the misc node present:
  `rp1_hub75 49152 0` and `crw------- 1 root root 10,123 /dev/rp1-hub75`.
- A fresh known-good PIO run completed on `totem4` and reported `frames=1887 submits=1887 elapsed_s=10.005 hz=188.61 words=58176 pack_us=9906`, but the corresponding all-16 Logic2 export still contains only two samples and zero edges on every captured channel:
  [`/Users/lampe/code/heart/.captures/20260512-pio-baseline-live2-all16/digital.csv`](/Users/lampe/code/heart/.captures/20260512-pio-baseline-live2-all16/digital.csv).
- A direct `pinctrl` sanity check on `totem4` does change GPIO5 locally from `lo` to `hi`, confirming the command path itself works:
  `5: op dl pn | lo` then `5: op dh pn | hi`.
- Even with that bench-side control path available, the fresh all-16 manual-toggle capture still exported two static rows with no observed edges and only the same static highs on Logic channels `9` and `11`:
  [`/Users/lampe/code/heart/.captures/20260512-manual-toggle-live-all16/digital.csv`](/Users/lampe/code/heart/.captures/20260512-manual-toggle-live-all16/digital.csv).

#### Interpretation

- This is still not a kernel-waveform failure. It is an instrumentation failure upstream of scoring.
- The new CLI remap support is useful once the analyzer starts seeing real edges, but today it does not change the result because there is no observed activity to remap.
- Per [`AGENTS.md`](/Users/lampe/code/heart/AGENTS.md), more kernel tuning should wait until a deliberate channel-identification pass shows at least one measured edge on the Logic capture.

#### Concrete next directions

1. Run a single-channel identification pass with one GPIO toggled at a time while probing the Saleae inputs physically, starting from the stuck-high Logic channels `9` and `11`.
1. Once one measured edge exists, use `scripts/hub75_score_capture.py --signal ...` to test alternate channel maps directly against the shifted-capture workflow before resuming kernel waveform optimization.
1. After the analyzer path is credible again, collect the three captures in order: known-good PIO baseline, one-pin GPIO sanity pulse, then the custom-kernel candidate.

#### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/heart/.captures/20260513-pio-baseline-live/digital.csv /Users/lampe/code/heart/.captures/20260512-pio-baseline-live2-all16/digital.csv`
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && HEART_PI5_SIMPLE_PROBE_LOG=0 HEART_PI5_SIMPLE_PROBE_SECONDS=10 HEART_PI5_SIMPLE_PROBE_PWM_BITS=6 HEART_PI5_SIMPLE_PROBE_CLOCK_DIVIDER=8 HEART_PI5_SIMPLE_SCAN_LSB_DWELL_TICKS=16 /home/michael/.cargo/bin/cargo run --quiet --bin pi5_simple_probe'`
- `ssh michael@totem4.local 'bash -lc '"'"'set -eu; pinctrl get 5; pinctrl set 5 op dl; pinctrl get 5; pinctrl set 5 dh; pinctrl get 5; pinctrl set 5 ip pn; pinctrl get 5'\"'\"''`
- Logic2 MCP timed captures on channels `0..15` at `125 MS/s`

## 2026-05-13

### Same-day capture-path recheck: instrumentation fault confirmed

#### What changed

- Extended [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so whole-capture diagnostics now preserve per-channel initial/final levels, not just edge counts.
- Updated [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py) to emit that per-channel activity in the JSON payload.
- Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with assertions that electrically silent captures retain stable high/low state information instead of collapsing to an uninformative empty diagnosis.
- Recorded the new live-capture artifacts in [`docs/hub75_kernel_signal_baselines.json`](/Users/lampe/code/heart/docs/hub75_kernel_signal_baselines.json) and the new bench rule in [`AGENTS.md`](/Users/lampe/code/heart/AGENTS.md).

#### Live observations

- On `totem4`, the custom module is still loaded and `/dev/rp1-hub75` exists:
  `rp1_hub75 49152 0` and `crw------- root root /dev/rp1-hub75`.
- A same-day PIO baseline rerun through Logic2 MCP still exported an electrically silent CSV on the expected `0..6` channel map:
  [`/Users/lampe/code/heart/.captures/20260513-pio-baseline-live/digital.csv`](/Users/lampe/code/heart/.captures/20260513-pio-baseline-live/digital.csv).
- A same-day all-16-channel discovery capture during that same known-good PIO run also showed zero edges across every Saleae digital channel, with only static highs on channels `9` and `11`:
  [`/Users/lampe/code/heart/.captures/20260513-pio-all16-live/digital.csv`](/Users/lampe/code/heart/.captures/20260513-pio-all16-live/digital.csv).
- A slower, more granular isolation test also failed the same way:
  while `totem4` manually toggled expected HUB75 GPIO pins `13`, `5`, `6`, and `12`, the all-16-channel Logic2 export still showed zero observed edges and only the same static highs on channels `9` and `11`:
  [`/Users/lampe/code/heart/.captures/20260513-manual-toggle-all16/digital.csv`](/Users/lampe/code/heart/.captures/20260513-manual-toggle-all16/digital.csv).

#### Interpretation

- This run did not uncover a kernel-waveform defect. It falsified the current measurement path itself.
- Because a known-good PIO run and a slow manual GPIO toggle both look electrically dead to the analyzer, the next blocker is probe routing, fixture grounding, or Logic channel assignment, not RP1 worker timing.
- The new diagnostic payload is now specific enough to prove that statement from saved artifacts alone:
  the all-16-channel manual-toggle capture is `electrically_silent` with `static_high_channels_present`, and the only persistent highs are channels `9` and `11`.

#### Concrete next directions

1. Run a deliberate bench-side channel-identification pass that physically maps Saleae channels to the expected HUB75 or GPIO pins, starting with the currently stuck-high channels `9` and `11`.
1. Verify analyzer ground and reference placement before reopening software tuning. The current artifacts are consistent with a disconnected probe bundle or a reference path issue.
1. Once any real edge is visible again, rerun the same three captures in order:
   known-good PIO on `0..6`, all-16 PIO discovery, then manual GPIO toggle sanity. Only after those pass should the kernel-path bridge resume.

#### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/heart/.captures/20260513-pio-baseline-live/digital.csv /Users/lampe/code/heart/.captures/20260513-manual-toggle-all16/digital.csv`
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && HEART_PI5_SIMPLE_PROBE_LOG=0 HEART_PI5_SIMPLE_PROBE_SECONDS=10 HEART_PI5_SIMPLE_PROBE_PWM_BITS=6 HEART_PI5_SIMPLE_PROBE_CLOCK_DIVIDER=8 HEART_PI5_SIMPLE_SCAN_LSB_DWELL_TICKS=16 /home/michael/.cargo/bin/cargo run --quiet --bin pi5_simple_probe'`
- Logic2 MCP timed captures on channels `0..6` and `0..15` at `250 MS/s` and `125 MS/s`
- `ssh michael@totem4.local 'bash -lc '"'"'set -eu; for pin in 13 5 6 12; do pinctrl set $pin op dl; sleep 0.01; pinctrl set $pin dh; sleep 0.01; pinctrl set $pin dl; sleep 0.01; pinctrl set $pin ip pn; done'"'"''`

## 2026-05-12

### Capture diagnosis split: silent export vs map mismatch

#### What changed

- Added whole-capture diagnosis helpers to [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so failed `0..1` similarity runs now distinguish:
  - `electrically_silent`
  - `possible_channel_map_mismatch`
  - `invalid_hub75_waveform`
- Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with explicit regressions for a globally silent CSV and a synthetically shifted live waveform on unmapped channels.
- Updated [`scripts/hub75_score_capture.py`](/Users/lampe/code/heart/scripts/hub75_score_capture.py) to emit those diagnoses alongside the existing similarity payload.

#### Live observations

- The local Logic automation preflight still fails in this environment:
  - Python package `saleae` missing in the selected interpreter
  - no local Logic app found in the standard install paths
- The saved artifacts in [`/Users/lampe/code/heart/.captures`](/Users/lampe/code/heart/.captures) remain unusable as electrical baselines, but the new diagnosis is more specific than before:
  - [`20260512-pio-baseline/digital.csv`](/Users/lampe/code/heart/.captures/20260512-pio-baseline/digital.csv) diagnoses as `electrically_silent`
  - [`20260512-rp1h-bridge/digital.csv`](/Users/lampe/code/heart/.captures/20260512-rp1h-bridge/digital.csv) diagnoses as `electrically_silent`
  - [`20260512-all-channels/digital.csv`](/Users/lampe/code/heart/.captures/20260512-all-channels/digital.csv) also shows zero edges across every captured column, so the current saved exports are not merely suffering from a `0..6` signal-map mismatch inside the CSV itself
- That means the immediate artifact problem is upstream of the scorer:
  either the Saleae session/export path captured no real transitions, or the probe/run timing did not coincide with a live drive window.

#### Interpretation

- The scorer is now strong enough to reject two distinct false positives:
  dead-capture similarity and live-but-miswired channel maps.
- For the current saved artifacts, the result is the first case, not the second one. The next measurement loop therefore needs a fresh capture path more than another scoring tweak.

#### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py .captures/20260512-pio-baseline/digital.csv .captures/20260512-rp1h-bridge/digital.csv`
- `./.venv/bin/python -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path('src').resolve())); from heart.utilities.hub75_logic_score import summarize_logic_channels; print(summarize_logic_channels('.captures/20260512-all-channels/digital.csv')[:8])"`

### Flatline baseline rejection

#### What changed

- Checkpoint commit: `767f6254` (`Reject flatline HUB75 baselines`)
- Tightened [`src/heart/utilities/hub75_logic_score.py`](/Users/lampe/code/heart/src/heart/utilities/hub75_logic_score.py) so each capture summary now declares whether it contains enough LAT/CLK activity to qualify as a real HUB75 waveform.
- Added a validity gate to the similarity score so invalid baseline/candidate pairs score `0.0` instead of falsely reporting a perfect electrical match.
- Extended [`tests/utilities/test_hub75_logic_score.py`](/Users/lampe/code/heart/tests/utilities/test_hub75_logic_score.py) with a regression that rejects flatline-vs-flatline CSV pairs.

#### Live observations

- The current saved local artifacts in [`/Users/lampe/code/heart/.captures`](/Users/lampe/code/heart/.captures) are still only `2` samples each, with no LAT or CLK edges.
- Before this change, those dead exports scored as `1.0` against each other, which made them unsafe as optimization baselines.
- On `totem4`, the custom `rp1_hub75` module is loaded and `/dev/rp1-hub75` exists; `dmesg` still shows `RP1H_START_WORKER` only entering the external-vsync path, not an internal scan engine.
- The Logic2 connector regressed to `Cannot switch sessions while recording` again during this run, so no fresh PIO baseline or bridged-kernel waveform could be exported.

#### Interpretation

- The most urgent measurement bug was not in the kernel worker; it was in the scoring loop accepting electrically dead captures as valid.
- That is fixed locally now: until a capture shows at least two LAT rises, one row interval, and measurable CLK activity, it cannot serve as a baseline or candidate score anchor.
- The bench is therefore blocked on Saleae session cleanup and channel recovery, not on rediscovering module load state.

#### Validation

- `./.venv/bin/pytest tests/utilities/test_hub75_logic_score.py`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/heart/.captures/20260512-pio-baseline/digital.csv /Users/lampe/code/heart/.captures/20260512-rp1h-bridge/digital.csv`
- `ssh michael@totem4.local 'grep -w rp1_hub75 /proc/modules; stat -c "devnode=%n mode=%a major=%t minor=%T" /dev/rp1-hub75; sudo -n dmesg | tail -n 40 | grep -i "rp1\\|hub75"'`

### Transport-only fail-fast follow-up

#### What changed

- Checkpoint commit: `a034299a` (`Fail fast on transport-only rp1-hub75 path`)
- Updated [`src/runtime/rp1_hub75.rs`](https://github.com/Organization5762/heart-rgb-matrix-driver/blob/f62c3cedc54d74a3e950d15efe356ca000b7756b/src/runtime/rp1_hub75.rs) so `HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE` is now opt-in instead of default-on.
- Added a runtime guard that errors after `8` queued frames with no `frames_presented` or `vsync_count` progress, configurable via `HEART_RP1_HUB75_REQUIRE_PROGRESS_AFTER_QUEUED_FRAMES`.
- Documented that fail-fast behavior in the [standalone driver README](https://github.com/Organization5762/heart-rgb-matrix-driver/blob/f62c3cedc54d74a3e950d15efe356ca000b7756b/README.md).

#### Live observations

- The active `logic2` connector became unreliable in this session: triggered and timed captures both hung before export, so this run did not produce a fresh electrical baseline.
- Existing fallback captures in [`/Users/lampe/code/heart/.captures`](/Users/lampe/code/heart/.captures) were not usable as baselines either:
  both the saved PIO and `rp1h` CSVs contained only `2` samples and `0` observed edges on every control line.
- The more important finding came from the code and docs, not the broken capture files:
  `rp1-hub75` is still explicitly transport-only, and the Rust backend had been masking that fact by self-issuing software vsync by default.

#### Interpretation

- Before this change, `/dev/rp1-hub75` could appear healthy in userspace counters even when no RP1 timing worker was consuming the queue.
- With software-vsync disabled by default and the progress gate in place, the current custom-kernel path now fails loudly instead of pretending a flatline path is electrically alive.
- That is a prerequisite for honest 0..1 similarity tuning: the next waveform experiment must involve a real worker, not just the packer queue.

#### Validation

- `PYO3_PYTHON=/Users/lampe/.local/bin/python3.12 cargo test --manifest-path ../heart-rgb-matrix-driver/Cargo.toml rp1_hub75 -- --nocapture`

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
1. Fix `/dev/rp1-hub75` access semantics for non-root runtime use, either with a device-mode policy or a userspace wrapper that is explicit and reproducible.
1. Once capture is live, run the red-only kernel submitter and the known-good PIO submitter through the same CSV scorer, then optimize the kernel path for `>=1000 Hz` without regressing control ordering or clock-shape similarity.

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
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && sudo ./target/debug/rp1_hub75_color_loop 2000 0'`
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && rm -f /tmp/rp1h_loop.log && (sudo ./target/debug/rp1_hub75_color_loop 5000 0 >/tmp/rp1h_loop.log 2>&1 &) ; sleep 0.5; pinctrl get 5,6,12,13,16,17,18,20,21,22,23,24,26,27; wait; tail -n 20 /tmp/rp1h_loop.log'`

## 2026-05-12 Red-only device bring-up

### What changed

- Added a deterministic solid-color mode to [`src/bin/rp1_hub75_color_loop.rs`](https://github.com/Organization5762/heart-rgb-matrix-driver/blob/f62c3cedc54d74a3e950d15efe356ca000b7756b/src/bin/rp1_hub75_color_loop.rs) via `HEART_RP1_HUB75_COLOR_LOOP_SOLID`.
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
1. Run that bridge against the existing `state32-...` core1 worker while the red-only submitter queues frames through `/dev/rp1-hub75`.
1. Once Logic2 capture is unblocked, score that bridged waveform against the known-good PIO baseline with the existing scorer.

### Validation

- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `scp /Users/lampe/code/heart-rgb-matrix-driver/src/bin/rp1_hub75_color_loop.rs michael@totem4.local:/home/michael/heart-rgb-matrix-driver/src/bin/rp1_hub75_color_loop.rs`
- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && sudo env HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1 HEART_RP1_HUB75_COLOR_LOOP_SOLID=red ./target/debug/rp1_hub75_color_loop 1000 0'`

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
1. Once capture is trustworthy, record a one-plane PIO baseline and a one-plane bridged-kernel capture under the same threshold/channel map, then score those with the existing `0..1` harness.
1. If the live one-plane waveform is clean, move the bridge boundary inward:
   either expose the pending slot more explicitly in the UAPI header or land an RP1-side/in-kernel consumer so the queue no longer depends on a polling userspace copier.
1. After the one-plane bridge is electrically proven, revisit higher PWM publication, because the current `0xc000` publication workaround is only sized for the one-plane bring-up shape.

### Validation

- `ssh michael@totem4.local 'cd /home/michael/heart-rgb-matrix-driver && /home/michael/.cargo/bin/cargo +stable build --quiet --bin rp1_hub75_color_loop'`
- `scp /Users/lampe/code/heart/scripts/rp1_hub75_bridge_state32.c michael@totem4.local:/home/michael/rp1-pio/rp1_hub75_bridge_state32.c`
- `ssh michael@totem4.local 'cd /home/michael/rp1-pio && gcc -O2 -Wall -Wextra -o rp1_hub75_bridge_state32 rp1_hub75_bridge_state32.c'`
- `ssh michael@totem4.local 'set -eu; cd /home/michael/rp1-pio; rm -f /tmp/rp1h_candidate.log /tmp/rp1h_submitter.log /tmp/rp1h_bridge.log; ( RP1_HUB75_SEED_SOLID=red ./rp1_hub75_run_candidate.sh state32-dsramcache-copy11plane-clkout-addrsetupnop8-seedoe-copydelay5-splithead1-allslow-lat2-clknop-regcount-dwell1 8 >/tmp/rp1h_candidate.log 2>&1 ) & candidate_pid=$!; sleep 0.8; ( cd /home/michael/heart-rgb-matrix-driver && sudo -n env HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS=1 HEART_RP1_HUB75_COLOR_LOOP_SOLID=red HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE=0 ./target/debug/rp1_hub75_color_loop 5000 0 >/tmp/rp1h_submitter.log 2>&1 ) & submitter_pid=$!; sleep 0.8; ( cd /home/michael/rp1-pio && sudo -n ./rp1_hub75_bridge_state32 5 /dev/rp1-hub75 0xc000 1 >/tmp/rp1h_bridge.log 2>&1 ) & bridge_pid=$!; wait $bridge_pid; wait $submitter_pid || true; wait $candidate_pid || true; tail -n 20 /tmp/rp1h_candidate.log; tail -n 20 /tmp/rp1h_submitter.log; tail -n 20 /tmp/rp1h_bridge.log'`
- `ssh michael@totem4.local 'printf \"%s\\n\" \"candidate\"; tail -n 30 /tmp/rp1h_candidate.log; printf \"%s\\n\" \"submitter\"; tail -n 30 /tmp/rp1h_submitter.log; printf \"%s\\n\" \"bridge\"; tail -n 30 /tmp/rp1h_bridge.log'`
- `./.venv/bin/python scripts/hub75_score_capture.py /Users/lampe/code/heart/.captures/20260512-pio-baseline/digital.csv /Users/lampe/code/heart/.captures/20260512-rp1h-bridge/digital.csv`
