# RP1 HUB75 Totem Blue Reproduction

This note records the reproducible Heart/RP1 path that produced a visually good
blue image on `totem3` on 2026-05-18.

## Known-good target state

| Item | Value | Direction |
|---|---|---|
| Target | `michael@totem3.local` | exact |
| Heart checkout | `/Users/lampe/code/heart` on branch `lampe/yep` | exact |
| Heart Linux bundle | `rp1/linux/files` | exact |
| Driver module srcversion | `DAC57640AA92F9BAD6C30F9` | exact |
| Driver module sha256 | `243a23ffb5195c0196cb117b8530c04aa870c2d0a3aa0867b054a794b3d02141` | exact |
| Payload sha256 | `f6b9097de3288f093b659b2a15cc7ee9da519349faf96c7badb8a98e4e8a5786` | exact |
| Candidate | `state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2` | exact |
| PWM bits | `6` | exact |
| Slot control offset | `0xb800` | exact |
| Dwell shift limit | `7` | exact |
| Expected counter rate | about `483/s` | higher better |

## One-command reproduction

From `/Users/lampe/code/heart`:

```sh
scripts/rp1_hub75_reproduce_totem_blue.sh michael@totem3.local
```

The script builds and deploys the `rp1-hub75` module directly from the
Heart-owned Linux bundle under `rp1/linux/files`, syncs the bundled RP1 selftest
sources to `/home/michael/rp1-pio`, builds the required helpers, enforces the
known-good payload hash, reports the module srcversion and module SHA-256,
publishes a solid blue slot, and starts the scanner candidate. It does not
require a local Linux checkout. Set `RP1_HUB75_STRICT_HASHES=1` to enforce the
two module checks too; the compatibility default `0` reports module mismatches
without rejecting the run.

The proven path is `totem3`. Earlier `totem5` examples in this note were
documentation drift, not a separate validated reproduction.

The consolidated runner exposes the same path and makes hash policy explicit:

```sh
./scripts/hub75_experiment.py plan totem3-known-good-blue \
  --target michael@totem3.local --strict-hashes
./scripts/hub75_experiment.py run totem3-known-good-blue \
  --target michael@totem3.local --strict-hashes
```

Expected successful tail:

```text
offset=0xf004 ... rate=500.../s
per_panel_fps=500...
aggregate_fps=2000...
verdict=PASS
```

## Manual command

If the target already has the matching module and `/home/michael/rp1-pio`
artifacts:

```sh
ssh michael@totem3.local 'cd /home/michael/rp1-pio && \
  sudo ./rp1_hub75_publish_regular_green_slot 0xb800 7 6 /dev/rp1-hub75 blue && \
  sudo env RP1_HUB75_PWM_BITS=6 ./rp1_hub75_run_candidate.sh \
    state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2 5'
```

## Static 4x1 Transport Image

The proven scanner accepts a `256x64` RGB888 strip. The packer emits transport
columns as `[A,C]`, then `[B,D]`, so logical panels remain ordered `A B C D`
across x. Heart should render the totem face as that `256x64` `A B C D` strip;
the native driver should pass it through as the regular-chain2 transport frame.
A raw frame must therefore be exactly `49152` bytes.

For the sun GIF currently on `totem3`, this publishes a static first frame into
the same slot without changing the scanner:

```sh
ssh michael@totem3.local 'cd /home/michael/rp1-pio && \
  ffmpeg -v error -i heart-sun-64.gif \
    -vf "scale=64:64:flags=lanczos,split=4[a][b][c][d];[a][b][c][d]hstack=inputs=4,format=rgb24" \
    -frames:v 1 -f rawvideo -pix_fmt rgb24 /tmp/heart-sun-256x64.rgb && \
  sudo ./rp1_hub75_publish_regular_green_slot \
    0xb800 7 6 /dev/rp1-hub75 blue all state32 /tmp/heart-sun-256x64.rgb'
```

## Last proof

| Measurement | Value | Direction |
|---|---:|---|
| Counter rate | `483.482/s` | higher better |
| Per-panel fps | `483.482` | higher better |
| Aggregate fps | `1933.928` | higher better |
| Verdict | `PASS` | exact |

The visually inspected output was blue horizontal bands after switching to the
OE-off-during-shift sequence. Use green only for hzeller baselines, not for this
Heart path.
