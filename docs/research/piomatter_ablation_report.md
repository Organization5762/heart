# Piomatter Parity Ablation Report

## Problem

Summarize the Piomatter-parity optimization work, quantify the relative impact of
the changes that were tried, and separate trustworthy wins from experiments that
looked fast but did not preserve the intended panel semantics.

This report is intentionally scoped to parity and benchmark work. Piomatter is
no longer part of the production runtime path in this repo.

## Materials

- [`scripts/benchmark_piomatter_row_repeat.py`](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/benchmark_piomatter_row_repeat.py)
- [`scripts/prepare_piomatter_parity_checkout.py`](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/prepare_piomatter_parity_checkout.py)
- [`scripts/run_piomatter_row_repeat_cycle.py`](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/run_piomatter_row_repeat_cycle.py)
- [`scripts/piomatter_rgb_cycle.py`](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/piomatter_rgb_cycle.py)
- [`rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/bench/piomatter_row_pattern_cost.rs)
- [`rust/heart_rgb_matrix_driver/src/runtime/tests.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/tests.rs)
- [`rust/heart_rgb_matrix_driver/pio/piomatter_row_repeat_engine_parity.pio`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_repeat_engine_parity.pio)
- [`rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_engine_parity.pio`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_compact_engine_parity.pio)
- [`rust/heart_rgb_matrix_driver/pio/piomatter_row_hybrid_engine_parity.pio`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_hybrid_engine_parity.pio)
- [`rust/heart_rgb_matrix_driver/pio/piomatter_row_window_engine_parity.pio`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_row_window_engine_parity.pio)

## Method

All serious Pi measurements were taken as grouped runs:

1. baseline pre
1. experiment
1. baseline post

The benchmark harness rejects:

- implausible wins above the shift-only ceiling
- groups whose baseline drifts too far between pre and post

That matters because several protocol experiments increased transfer-loop
cadence without preserving a believable full-frame scan behavior.

## Executive Summary

The consistent conclusions were:

- The largest trustworthy wins came from reducing scan work, not from larger
  slabs or moving between userspace and kernel-space models.
- The RP1 MMIO path outperformed the DMA-heavy path for the tested Piomatter
  parity workloads.
- `row-compact` is the safest general-purpose parity protocol that still
  preserves the Piomatter-visible GPIO waveform.
- More aggressive structured-row encodings can help a lot on sparse scenes, but
  only when the scene shape matches the encoding exactly.
- Several experiments reduced FIFO bytes dramatically while leaving PIO cycles
  flat or worse. Those wins were not enough on their own.

## Trustworthy Hardware Results

These measurements came from grouped runs that stayed below the plausibility
ceiling and did not show large baseline drift.

### Scan-quality and frequency levers

For the `256x64` four-panel case, the biggest lever was reducing scan passes:

| Configuration | Measured refresh |
| --- | --- |
| `8 planes, 2 temporal, 27 MHz` | about `62.6-66.3 Hz` |
| `8 planes, 0 temporal, 27 MHz` | about `113.2 Hz` |
| `6 planes, 0 temporal, 27 MHz` | about `170.5 Hz` |
| `5 planes, 0 temporal, 27 MHz` | about `185.7 Hz` |
| `4 planes, 0 temporal, 27 MHz` | about `244.9 Hz` |
| `6 planes, 0 temporal, 100 MHz` | about `186.5 Hz` |
| `5 planes, 0 temporal, 100 MHz` | about `199.8 Hz` |
| `4 planes, 0 temporal, 100 MHz` | about `275.8 Hz` |

Implication:

- reducing `n_planes` and `n_temporal_planes` was a first-order lever
- pushing the target frequency higher was a second-order lever

### Transfer-path findings

The most important transport result was negative: the system was not primarily
limited by “needs more DMA.”

Grouped runs on `256x64`, `5 planes`, `0 temporal`, `100 MHz` showed:

- MMIO enabled: about `1185 Hz` on `solid-red`
- forced DMA (`tx_use_mmio=N`): about `356 Hz`

Implication:

- the RP1 MMIO path was materially better than forcing DMA for these workloads

Larger transfer chunks did help slightly on the upgraded kernel:

| Setting | Result |
| --- | --- |
| `MAX_XFER=65532` | about `282.0 Hz` |
| `MAX_XFER=262140` | about `286.2 Hz` |

That is only about a `+1.5%` to `+1.6%` improvement. It is worth keeping, but
it is not the main bottleneck.

`tx_reuse_desc=Y` also helped slightly:

- about `+0.15%` to `+0.2%`

Other driver/module sweeps were flat or regressed:

- `tx_mmio_user_pages_min_bytes=0`
- SRAM-backed TX
- `tx_ioctl_coalesce_bytes=0`

### Protocol variants

#### `row-repeat`

This was the first clearly useful protocol shift. It reduced host traffic on
flat rows and delivered a large gain over stock Piomatter on static scenes.

Representative result on a `64x64` static frame:

- stock Piomatter: about `91.4 fps`
- `row-repeat`: about `310 fps`

That was a real win, but still below the shift-only ceiling.

#### `row-compact`

`row-compact` moved fixed trailer behavior into PIO and became the safest
general-purpose experimental baseline.

Representative grouped Pi results:

- `quadrants`: about `264.8 Hz` baseline vs `269.9 Hz` experiment
- `solid-red`: about `349.2 Hz` baseline vs `356.0 Hz` experiment

Typical lift:

- about `+1.6%` to `+2.2%`

That is modest, but repeatable.

#### `row-window`

`row-window` helped meaningfully on center-weighted sparse scenes.

Representative grouped Pi result on `center-box`, `256x64`, `5 planes`,
`0 temporal`, `100 MHz`:

- `row-compact`: about `1066 Hz`
- `row-window`: about `1189 Hz`

Lift:

- about `+11.5%`

This was the best trustworthy scene-specific optimization.

#### `row-hybrid`

`row-hybrid` produced the largest scene-specific win in one structured test:

- `quadrants`: about `286-290 Hz` baseline vs about `466.5 Hz`

That is roughly a `+62%` lift.

However, it was not stable enough across follow-up runs to treat as the default
best-known protocol.

## Local Simulator Ablations

The most reproducible current local baseline is the row-pattern cost benchmark:

```bash
cargo run --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --bin piomatter_row_pattern_cost -- --pattern all
```

Current output from this tree:

### `dark-row`

| Variant | Words | Cycles |
| --- | --- | --- |
| `row-repeat` | `9` | `148` |
| `row-compact` | `5` | `148` |
| `row-compact-tight` | `5` | `144` |
| `row-counted` | `6` | `146` |
| `row-hybrid` | `5` | `150` |
| `row-runs` | `5` | `149` |
| `row-split` | `5` | `149` |
| `row-window` | `5` | `141` |

### `repeated-blue`

| Variant | Words | Cycles |
| --- | --- | --- |
| `row-repeat` | `9` | `155` |
| `row-compact` | `5` | `149` |
| `row-compact-tight` | `5` | `147` |
| `row-counted` | `6` | `148` |
| `row-hybrid` | `5` | `151` |
| `row-runs` | `5` | `150` |
| `row-split` | `6` | `151` |
| `row-window` | `6` | `149` |

### `alternating`

| Variant | Words | Cycles |
| --- | --- | --- |
| `row-repeat` | `72` | `153` |
| `row-compact` | `68` | `149` |
| `row-compact-tight` | `68` | `147` |
| `row-counted` | `69` | `146` |
| `row-hybrid` | `68` | `149` |
| `row-window` | `69` | `146` |

### `quadrants`

| Variant | Words | Cycles |
| --- | --- | --- |
| `row-repeat` | `72` | `153` |
| `row-compact` | `68` | `149` |
| `row-compact-tight` | `68` | `147` |
| `row-counted` | `69` | `146` |
| `row-hybrid` | `7` | `154` |
| `row-runs` | `7` | `155` |
| `row-split` | `8` | `154` |
| `row-window` | `8` | `153` |

### `center-box`

| Variant | Words | Cycles |
| --- | --- | --- |
| `row-repeat` | `72` | `153` |
| `row-compact` | `68` | `149` |
| `row-compact-tight` | `68` | `147` |
| `row-counted` | `69` | `146` |
| `row-hybrid` | `68` | `149` |
| `row-runs` | `9` | `160` |
| `row-window` | `9` | `154` |

Interpretation:

- `row-compact` and `row-counted` are the best broad “safe” improvements
- `row-hybrid`, `row-runs`, `row-split`, and `row-window` can slash words on
  structured rows, but often do not reduce cycles
- scene-specific protocols only pay off when the input pattern actually matches
  the encoding

## Experiments That Did Not Hold Up

These are worth calling out so future work does not repeat them blindly.

### Slab batching

Repeating one frame blob into `x4`, `x8`, or `x16` slabs did not improve steady
refresh meaningfully once the path was already stable.

Conclusion:

- slabs reduce submit frequency
- they did not materially improve actual scan throughput on the measured paths

### Higher target frequency alone

Increasing the Piomatter target clock above about `100 MHz` stopped helping in a
meaningful way on the tested configurations.

Representative finding:

- `3 planes, 0 temporal, 100 MHz`: about `388.7 Hz`
- `3 planes, 0 temporal, 200 MHz`: about `388.1 Hz`

Conclusion:

- the remaining boundary is not just “run the SM faster”

### Aggressive structured-row protocols without stronger parity

Some variants produced implausibly high numbers that exceeded the shift-only
ceiling or otherwise failed grouped-run sanity checks.

Conclusion:

- row-level parity is not enough for these protocols
- future aggressive protocols need full-frame parity, not only per-row parity

## Proposed Keep/Back Out Decisions

### Keep

- grouped Pi benchmark methodology in the benchmark harness
- plausibility ceiling checks
- larger `MAX_XFER` default (`262140`)
- `row-compact` as the safest general parity protocol
- `row-window` as a targeted sparse-scene optimization
- RP1 MMIO path as the preferred transport mode for current parity runs
- local row-pattern cost benchmark as the standard ablation tool

### Do Not Promote Yet

- `row-hybrid`
- `row-runs`
- `row-split`
- `row-counted` as the hardware default
- any protocol that only proves row-level parity

## Recommendation

If the goal is a practical “best known” parity setup today:

- use `row-compact` as the default experimental protocol
- use `row-window` only for center-box-like sparse scenes
- default RP1 PIO parity runs to MMIO (`tx_use_mmio=Y`)
- leave MMIO enabled
- keep `MAX_XFER=262140`
- treat `5 planes, 0 temporal, 100 MHz` as the current quality/performance
  compromise for the four-panel case

If the goal is another large speed step, the next work should not be another
small trailer optimization. It should be:

1. full-frame parity for structured protocols
1. a protocol change that lowers actual PIO cycles, not only FIFO bytes
1. more scene-aware protocol selection only after that full-frame parity exists

## Validation

- `cargo run --manifest-path rust/heart_rgb_matrix_driver/Cargo.toml --bin piomatter_row_pattern_cost -- --pattern all`
