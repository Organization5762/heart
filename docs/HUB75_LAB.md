# HUB75 Hardware Laboratory

This is the calm entrypoint for retained HUB75 experiments:

```sh
./scripts/hub75_experiment.py list
./scripts/hub75_experiment.py list --json
./scripts/hub75_experiment.py plan runtime-color-cycle
```

`list --json` names the parameters each experiment actually applies. `plan`
prints only applied settings and fixed invariants. A non-default option that an
experiment cannot apply is rejected before any hardware mutation.

Temporal PWM is forbidden. The runner has no temporal-plane or temporal
brightness control.

## T1–T5 status

- [x] T1: inventory the exact 27 pre-consolidation scripts.
- [x] T2: centralize configuration, SRAM validation, capture, scoring, and
  deployment logic.
- [x] T3: expose promoted experiments through one parameterized runner.
- [x] T4: retire the approved 6 replaced and 17 superseded/one-off scripts
  with full-SHA recovery locators and preserved conclusions.
- [x] T5: document every retained experiment and supporting command.

The machine-checkable inventory is
[`docs/hub75_script_inventory.json`](hub75_script_inventory.json). It records
the original path, classification, disposition, replacement, preserved
conclusion, and a full-SHA recovery locator for every row.

## Retained command matrix

Run `plan` before `run` when changing any value.

| Experiment | Exact command | Applied settings | Fixed safety contract | Expected result |
|---|---|---|---|---|
| Runtime color cycle | `./scripts/hub75_experiment.py run runtime-color-cycle --rows 64 --cols 64 --chain-length 1 --parallel 1 --hardware-mapping adafruit-hat-pwm --led-rgb-sequence RGB --intensities 32,96,160,255 --seconds 2` | Geometry, wiring/color order, intensities, duration | No temporal PWM | Solid red, green, and blue fills at each intensity expose wiring and color-order faults. |
| Runtime gradient | `./scripts/hub75_experiment.py run runtime-gradient --rows 64 --cols 64 --chain-length 1 --parallel 1 --hardware-mapping adafruit-hat-pwm --led-rgb-sequence RGB --seconds 5` | Geometry, wiring/color order, duration | No temporal PWM | A moving full-frame gradient exposes ordering, continuity, and whole-frame transport faults. |
| Runtime single line | `./scripts/hub75_experiment.py run runtime-single-line --rows 64 --cols 64 --chain-length 1 --parallel 1 --hardware-mapping adafruit-hat-pwm --led-rgb-sequence RGB --row-index 0 --line-thickness 1 --red 255 --green 255 --blue 255 --seconds 5` | Geometry, wiring/color order, row, thickness, RGB, duration | No temporal PWM | One repeated line isolates address, latch, blanking, and cadence faults. |
| Direct GPIO smoke | `./scripts/hub75_experiment.py run gpio-smoke --rows 64 --cols 64 --gpio-diagnostic-mode scan --row-index 0 --row-dwell-seconds 0.0005 --red 255 --green 255 --blue 255 --seconds 5` | Geometry, mode, row, dwell, RGB, duration | GPIO18 and legacy GPIO4 mirror active-low OE | Slow GPIO scanout separates panel/bonnet wiring faults from transport faults. |
| Proven totem3 blue | `./scripts/hub75_experiment.py run totem3-known-good-blue --target michael@totem3.local --seconds 5 --strict-hashes` | Target, duration, hash enforcement | Self-contained Heart Linux bundle; 256x64 `A B C D`; fixed candidate/PWM 6/slot `0xb800`; no Rust color loop | About 483–500 counter increments/s and a stable blue output. |
| Regular P0/P1 direct | `./scripts/hub75_experiment.py run regular-p0p1-direct --target michael@totem3.local --seconds 5 --pwm-bits 6 --candidate state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2 --frame-slot-offset 0xb800` | Target, duration, PWM bits, candidate, frame slot | Regular P0/P1 chain2; fresh `0xb800` publication after payload load and before `START_MAGIC` | Audited packer-bypass scan with freshly published slot metadata. |

The payload hash is always enforced. For compatibility, module srcversion and
module SHA-256 are reported but not enforced by default. Pass `--strict-hashes`
to enforce the module hashes too. The plan JSON states which policy is in
effect. The proven target is `totem3`; earlier `totem5` examples in the
reproduction note were documentation drift, not a separate validated path.

`gpio-smoke` modes are `scan`, `hold-row`, `latch-pulse`, and `walking-bit`.
The legacy whole-panel `oe-toggle` mode is intentionally not promoted because
its user-controlled cadence was temporal brightness modulation. All
hardware-bound inputs are validated before execution; direct scanner candidate
names are restricted to launcher tokens containing only letters, digits,
periods, underscores, and hyphens.

## Shared SRAM gate

All values use offsets within the 64 KiB RP1 shared-SRAM window and half-open
ranges:

- payload: `[0x8000, payload_end)`
- aligned source: `[source_start, source_end)`
- reserved firmware mailbox: `[0xff00, 0x10000)`

The validator requires a positive power-of-two alignment, detects an escaped
range, requires `source_start >= align_up(payload_end, alignment)`, and requires
`source_end <= 0xff00`.

Examples:

```sh
# Documented 7,716-byte payload with a safe 16 KiB tail.
./scripts/hub75_experiment.py validate-sram \
  --payload-size 7716 --source-offset 0xa000 --source-size 0x4000 \
  --alignment 0x1000

# Documented 19,720-byte payload with an 8 KiB tail.
./scripts/hub75_experiment.py validate-sram \
  --payload-size 19720 --source-offset 0xd000 --source-size 0x2000 \
  --alignment 0x1000

# Rejected: [0xc000,0x10000) overlaps the mailbox.
./scripts/hub75_experiment.py validate-sram \
  --payload-size 7716 --source-offset 0xc000 --source-size 0x4000

# Rejected: a 90,112-byte state32 frame cannot fit in shared SRAM.
./scripts/hub75_experiment.py validate-sram \
  --payload-size 7716 --source-offset 0xc000 --source-size 90112
```

Do not treat `0x4000`, `0xa000`, `0xc000`, or `0xd000` as generally safe.
Safety depends on both payload end and source size.

## Trusted Logic2 capture and scoring

`capture` analyzes an already-exported Logic2 digital CSV. It does not start a
Logic2 acquisition. The Saleae package must be installed in the selected
Python environment, `/Applications/Logic 2.app` must exist (or be supplied
with `--logic2-application`), and the operator must attest that Logic2 is
available with no active recording blocking session switching.

The default connector map is:

| Signal | Channel | Signal | Channel |
|---|---:|---|---:|
| R1 | 0 | G1 | 8 |
| B1 | 1 | R2 | 2 |
| B2 | 3 | G2 | 13 |
| A | 4 | B | 11 |
| C | 5 | D | 10 |
| CLK | 6 | LAT | 9 |
| OE | 7 | E | unmapped |

Overrides use repeated `--signal NAME=CHANNEL`. Unknown signals, negative
channels, invalid integers, and duplicate assignments are rejected.

### 1. Prove the probes are on the intended host

Start a Logic2 recording first, then run the deliberate low-frequency CLK
toggle:

```sh
./scripts/hub75_experiment.py probe-toggle \
  --target-host michael@totem3.local \
  --proof-signal CLK --gpio 17 \
  --toggles 4 --interval-seconds 0.05 \
  --output .captures/totem3-probe-execution.json
```

The command stops and verifies absence of the shell scanner, holds active-low
OE blank/high on both GPIO18 and legacy GPIO4, toggles only CLK, and records the
safe preconditions and cleanup. It releases CLK but deliberately leaves both
OE candidates actively high/blank. The next retained experiment reclaims and
configures the pins.

Stop the Logic2 recording and export its digital CSV. Correlate the named CLK
channel with the hashed execution transcript:

```sh
./scripts/hub75_experiment.py probe-proof \
  .captures/totem3-probe/digital.csv \
  --target-host michael@totem3.local \
  --probe-host totem3.local \
  --proof-signal CLK \
  --execution-artifact .captures/totem3-probe-execution.json \
  --output .captures/totem3-probe-proof.json
```

Proof requires the expected edge count within one edge and every observed edge
interval within 35% of the deliberate cadence. Preflight re-hashes and
revalidates the proof CSV and execution transcript, target, signal, channel,
edge count, and cadence.

### 2. Export and accept an experiment capture

Start a new Logic2 recording, run the planned experiment, stop recording, and
export the digital CSV. Then analyze it:

```sh
./scripts/hub75_experiment.py capture \
  .captures/blue/digital.csv \
  --target-host michael@totem3.local \
  --probe-host totem3.local \
  --probe-proof .captures/totem3-probe-proof.json \
  --attest-logic2-session-ready \
  --expected-colors B1,B2
```

`--attest-logic2-session-ready` is explicitly operator attestation, not a
machine-verified session query. Trusted evidence additionally requires the
real Saleae module, correlated proof, a non-silent valid HUB75 waveform, and
mapped CLK/LAT/OE/A–D plus R1/G1/B1/R2/G2/B2.

Color validation is two-sided: declared active signals must be active or
static high, and every declared inactive color signal must remain static low.
Use `--expected-colors none` for black. Output reports every color channel,
clock, latch, address activity, active-low OE active/blank duty, the analyzed
CSV SHA-256, and proof provenance. `--diagnostic-only` can explain invalid or
silent exports but can never turn them into trusted comparison evidence.

### 3. Compare captures

```sh
./scripts/hub75_experiment.py score \
  .captures/baseline/digital.csv .captures/candidate/digital.csv \
  --target-host michael@totem3.local \
  --probe-host totem3.local \
  --probe-proof .captures/totem3-probe-proof.json \
  --attest-logic2-session-ready \
  --baseline-expected-colors B1,B2 \
  --candidate-expected-colors B1,B2
```

All similarity metrics are unitless `0..1` values where higher is better. The
complete score is:

| Component | Weight | Direction | Measurement |
|---|---:|---|---|
| Control/timing/address | 75% | Higher better | Validity-gated waveform timing, median-cycle OE active fraction, row-relative fault rates, and one authoritative address-transition rate per complete LAT interval |
| Color | 25% | Higher better | Per-channel transition rate per complete LAT-to-LAT interval; static levels are compared only when both channels are static |

The headline verdict passes only when both captures have trusted provenance and
electrical/pattern validity and the weighted score is at least `0.90`. The
75/25 split keeps scan integrity primary while ensuring real RGB divergence can
fail an otherwise identical control waveform; `0.90` allows a small measurement
budget without accepting a major component regression. The JSON keeps the raw
edge counts, initial/final levels, normalized `edges_per_lat_interval`, every
per-color score, the compared color-signal set, component scores, weights, and
threshold visible.

Acquisition-window length and dynamic-channel start/end phase are not score
inputs: event counts are normalized over complete LAT intervals. Static levels
remain significant for truly static channels. Whole-capture OE active/blank
duty and timing/address maxima remain visible diagnostics, but are not score
features because acquisition boundaries and longer sample windows can change
them; the score uses median-cycle OE duty, medians, p99 values, and normalized
event rates. This is an electrical regression heuristic, not an optical
brightness, image-quality, or seizure-safety measurement; captures still need
the declared-pattern and no-temporal-PWM gates. The
control/timing/address detail is named
`control_timing_address_detail` so it cannot be mistaken for the complete
comparison.

For a diagnostic image:

```sh
./scripts/hub75_experiment.py render-capture \
  .captures/blue/digital.csv --rows 64 --cols 64 \
  --weight-oe --output .captures/blue/virtual.png
```

OE-weighted reconstruction is diagnostic evidence, not a brightness
measurement.

## Linux bundle commands

The retained script is a thin compatibility entrypoint over
`heart.utilities.hub75_lab._bundle`, the authoritative implementation. The
calm runner exposes the same exact commands:

```sh
./scripts/hub75_experiment.py bundle list
./scripts/hub75_experiment.py bundle apply --linux /path/to/linux --dry-run
./scripts/hub75_experiment.py bundle apply --linux /path/to/linux
./scripts/hub75_experiment.py bundle diff --linux /path/to/linux
./scripts/hub75_experiment.py bundle deploy-target \
  --host michael@totem3.local \
  --remote-dir /home/michael/rp1-pio \
  --remote-module-dir /tmp/rp1-hub75-module
./scripts/hub75_experiment.py bundle preflight \
  --host michael@totem3.local --remote-dir /home/michael/rp1-pio
```

Direct compatibility invocation remains supported:

```sh
./scripts/rp1_hub75_linux_bundle.py --help
```

## Historical Piomatter parity results

Piomatter was an external baseline, not the production runtime. The trusted
ablation runs used `n_temporal_planes=0`. The historical “8 planes, 2
temporal” result is preserved only as evidence and must not be reproduced:
temporal brightness flicker is unsafe and visually unacceptable.

The useful retained conclusions are:

- MMIO was materially faster than forced DMA.
- Row-compact was the safest general parity protocol.
- Row-window helped only sparse scenes.
- Row-repeat reduced static-scene host traffic.
- Generated checkout overrides were research artifacts, not a reproducible
  production path.

## Retired low-level probes and recovery

The inventory preserves the reason each source is retired. In particular:

- `rp1_hub75_play_rgb888_frames.c` used `[0xc000,0x10000)`, overlapping the
  mailbox `[0xff00,0x10000)`.
- `rp1_hub75_play_state32_frames.c` assumed a 90,112-byte frame that cannot fit
  in 64 KiB shared SRAM.
- `rp1_hub75_play_slab_frames.c` wrote configuration at `0xff00`, the first
  mailbox byte.
- Other fixed `0xa000`, `0xc000`, and `0xd000` sources remain
  payload-size-dependent.
- The state32 bridge capture remained untrusted after the analyzer was shown to
  be attached to the wrong host.

To inspect any retired source without restoring it into the checkout, copy its
full `recovery_ref` from the inventory and run:

```sh
git show '<full-sha>:<exact-path>'
```

To recover it for isolated historical study:

```sh
git show '<full-sha>:<exact-path>' > /tmp/<original-basename>
```

Do not run recovered historical players against hardware without applying the
current SRAM, no-temporal-PWM, OE, and probe-host safety gates.
