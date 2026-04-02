# Pi 5 Scan Enhancement Ladder

## Materials

- [`rust/heart_rgb_matrix_driver/src/runtime/pi5_scan.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_scan.rs)
- [`rust/heart_rgb_matrix_driver/pio/pi5_simple_hub75.pio`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/pi5_simple_hub75.pio)
- [`rust/heart_rgb_matrix_driver/native/pi5_pio_scan_shim.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/native/pi5_pio_scan_shim.c)
- [`rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/heart_pi5_scan_loop.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/kernel/pi5_scan_loop/heart_pi5_scan_loop.c)
- [`rust/heart_rgb_matrix_driver/bench/pi5_pio_hub75_probe.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/pi5_pio_hub75_probe.rs)
- [`rust/heart_rgb_matrix_driver/src/runtime/pi5_pio_sim.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_pio_sim.rs)
- [`rust/heart_pio_sim/src/lib.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_pio_sim/src/lib.rs)
- [Adafruit_Blinka_Raspberry_Pi5_Piomatter](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter)
- [Piomatter `protomatter.pio`](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter/blob/main/src/protomatter.pio)
- [Piomatter `render.h`](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter/blob/main/src/include/piomatter/render.h)
- [Piomatter `pins.h`](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter/blob/main/src/include/piomatter/pins.h)

## Problem

The Pi 5 HUB75 path now has a working full-blue baseline again, but recent
failures showed that jumping straight from "something lights up" to
"optimization" is too risky. We need a fixed sequence for improvements:

- prove the behavior first in Piomatter or a Piomatter-equivalent minimal path
- port that exact behavior into `heart_rgb_matrix_driver`
- add one optimization at a time
- require a real-panel validation gate before moving on

This note turns that into a concrete ladder so future work does not mix
transport correctness, panel timing, and performance work in one step.

## Enhancement Table

| Phase | Enhancement | What Changes | Why It Matters | Main Risk | Validation Gate | Current Status |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Piomatter parity baseline | Reproduce a behavior first in Piomatter on the same panel, bonnet, and wiring profile. Record the exact pins, color order, and timing knobs that worked. | Prevents debugging two unknowns at once. | Porting a broken or unverified config into our stack and treating it as a transport bug. | Piomatter shows correct `RGBW`, blue-fill, checker, and row-bars on hardware first. | Required policy going forward. |
| 1 | Stable simple host-driven baseline | Keep the simple path literal and Piomatter-like: host-generated GPIO words, `LAT` and `OE` in-band, `CLK` in side-set, full-frame replay via `PackedScanFrame::pack_rgba()`. | Gives one known-good rollback point. | Losing the baseline while experimenting. | Full blue for 20 seconds, then `RGBW`, then `row-bars` on the same panel. | Working again for full blue. |
| 2 | Transfer diagnostics and failure surfacing | Instrument native submit/wait so `/dev/pio0` failures report exact context: command mix, expanded word count, PIOLib error code, and retry behavior. | Current "transfer submission failed" is too vague to debug regressions efficiently. | Hiding a transport bug behind panel symptoms. | Every submit failure prints enough information to explain whether it is content-dependent, size-dependent, or transient. | Needed next. |
| 3 | Userspace replay / retainment | Keep one already-packed simple frame resident in userspace and replay it without repacking or rebuilding intermediate buffers between refreshes. | Removes Python/host repaint artifacts while staying outside the kernel. | Stale frame ownership or replay-state bugs. | Static blue-fill and row-bars stay stable for 60 seconds without visible repainting. | Partially explored, not stable enough yet. |
| 4 | Kernel resident replay for the simple format | Port the known-good simple command stream into the kernel resident loop without changing scan semantics. | Moves the working waveform into hardware-owned steady-state refresh. | Reintroducing parser/config drift between userspace and kernel. | Kernel simple replay matches userspace simple replay visually on `RGBW`, blue-fill, and row-bars. | Not started on the current simple format. |
| 5 | Repeat / run-length compaction | Reintroduce repeat commands only after they are proven boundary-safe on live panels. Start with whole-row uniform runs, then carefully widen coverage. | Reduces transfer size on flat content. | Bold edge bars, cadence drift, or hidden repeat-boundary timing differences. | Blue-fill, checker, and row-bars look identical to the literal baseline while total submitted words drop. | Rolled back for now. |
| 6 | Optimized bit packing | Move from literal GPIO words to a packed parser-friendly stream once the simple path is stable. Keep `.pio`, native shim, kernel shim, and simulator on one generated spec. | Needed for better throughput and lower bandwidth. | Parser drift, side-set config mismatches, or packing bugs that simulation misses. | Simulator, audit tools, and hardware all agree on `RGBW`, checker, row-bars, and a full-frame image. | Deferred until simple replay is stable. |
| 7 | Double buffering and changed-frame turnover | Keep one active replay frame and one staging frame so changed-frame updates do not tear or stall refresh. | Improves animation responsiveness and changed-frame throughput. | Races between frame ownership, replay, and presentation accounting. | `distinct_frame_update_hz` improves on Pi without visible tearing. | Deferred. |
| 8 | Wiring, color-order, and panel-profile expansion | Support `adafruit-hat`, `adafruit-hat-pwm`, color-order variants, and panel quirks as explicit validated profiles. | Turns ad-hoc pin/color hacks into supported configurations. | Configuration matrix explosion with no clear baseline. | Each new profile first works in Piomatter, then in the simple path, then in any optimized path. | In progress for `adafruit-hat`; broader matrix deferred. |

## Recommended Work Order

Do not skip phases. The intended order is:

1. Phase 0: Piomatter parity
1. Phase 1: stable simple baseline
1. Phase 2: transfer diagnostics
1. Phase 3: userspace replay / retainment
1. Phase 4: kernel simple replay
1. Phase 5: repeat compaction
1. Phase 6: optimized bit packing
1. Phase 7: double buffering
1. Phase 8: profile expansion

## Near-Term Checklist

The next practical steps are:

1. Keep the current literal full-frame simple path as the baseline because it
   is the last known-good all-blue state.
1. Instrument the native submit path so "transfer submission failed" reports
   the exact reason.
1. Re-run `RGBW`, row-bars, and a static image after each transport change.
1. Re-enable repeat only after the literal path is stable for those probes.
