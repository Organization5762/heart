# Current HUB75 State

Hello hourly agent. You are taking over a Pi 5 / RP1 HUB75 debug thread for
Michael. The immediate goal is to keep improving the panel output on `totem4`
without regressing the working E-address-line fix.

## Hardware And Hosts

- Main repo: `/Users/lampe/code/heart`
- Custom Linux/selftest tree: `/Users/lampe/code/linux`
- Active selftest path:
  `/Users/lampe/code/linux/tools/testing/selftests/drivers/rp1-pio`
- SRAM/source-buffer map:
  `/Users/lampe/code/heart/docs/RP1_HUB75_SRAM_MAP.md`
- Target panel host: `michael@totem4.local`
- Staged target path on `totem4`: `/home/michael/rp1-pio`
- Panel work is currently focused on `totem4`.
- Recent color-profile validation also ran on `totem1` after Michael suspected
  a totem-specific electrical issue.
- Saleae Logic is available, but the latest electrical sanity pass showed the
  probes were observing `totem1`/that fixture, not `totem4`.

Known device nodes on `totem4`:

- `/dev/pio0`
- `/dev/rp1-hub75`

Important distinction: `/dev/rp1-hub75` currently exposes the custom kernel
interface/counters, but the visible panel output in this session came from the
RP1 core1 selftest/direct `PROC_RIO` path launched by
`rp1_hub75_run_candidate.sh`, not from a full kernel-worker GPIO driver.

Important SRAM rule: do not pick RP1 shared-SRAM source offsets by trial and
error. The core1 launcher uses `0x20007000`, payloads load at `0x20008000`, and
the firmware mailbox occupies `0x2000ff00..0x2000ffff`. `0x2000c000` only worked
for smaller payloads and overlaps the mailbox with a 16 KiB source buffer;
`0x20004000` overlaps firmware/launcher territory. Check
`docs/RP1_HUB75_SRAM_MAP.md` before changing any source base.

Fresh confirmation from this run:

- `rp1_hub75_color_loop` on `/dev/rp1-hub75` can queue and present frames at
  about `1850 Hz` in software.
- While it runs, `pinctrl get` still reports the HUB75 pins as `PIO*`, not a
  live GPIO-driving path. So the custom misc-device route still does not emit
  a measurable panel waveform yet.
- The `logic2` automation path is available through
  `/Users/lampe/.local/bin/uv run --with logic2-automation ...`.
- Latest capture status: Saleae sees real HUB75 waveforms while `totem1` is
  running, goes flat when `totem1` pins are forced low, and stays flat while
  `totem4` is actively running. Do not use current Saleae captures as evidence
  about `totem4` until the probes are physically moved or reidentified.

## Pin Map Under Test

Current software pin map:

| Role | GPIO |
| --- | --- |
| R1/G1/B1 | 5 / 13 / 6 |
| R2/G2/B2 | 12 / 16 / 23 |
| CLK/LAT/OE | 17 / 21 / 18 |
| A/B/C/D/E | 22 / 26 / 27 / 20 / 24 |

Compatibility note: the current state32 selftest scanner also mirrors OE onto
legacy GPIO4. Some Adafruit HAT-style HUB75 wiring expects OE on GPIO4 instead
of GPIO18. The scanner now configures GPIO4 as `PROC_RIO04`, seeds bit 4 in
state32 words when OE is blanked, and clears bit 4 alongside GPIO18 during OE
active dwell.

The key recent fix was adding and driving `E` on GPIO24. Before that, a 64x64
1/32-scan panel showed bands like `16 black, 16 red, 16 black, 16 red` because
rows 16-31 reused the row 0-15 address range.

After the fix, `pinctrl` on `totem4` showed GPIO24 under `PROC_RIO` control:

```text
24: a6    pn | hi // GPIO24 = PROC_RIO024
```

## Local Files Touched In `/Users/lampe/code/linux`

These files appear as untracked in the local Linux tree, so check before
assuming they are committed upstream:

- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_seed_state32.c`
  - Added `GPIO_E` / `PIN_E`.
  - Rows 16-31 now include `PIN_E` in `row_addr`.
  - Added legacy GPIO4 to `PIN_OE` so state32 buffers blank both OE pins.
- `tools/testing/selftests/drivers/rp1-pio/rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s`
  - Added `PAD_CTRL_ADDR_E`, `GPIO_E`, `PIN_E`.
  - Added `PIN_E` to `KEY_PINS` and `ADDR_OE_PINS`.
  - Configures GPIO24 as `PROC_RIO`.
  - Fixed `local_row_addr_masks` order: rows 0-15 no E, rows 16-31 with E.
  - Added `USE_RGB333_EXPAND_CACHE`, which expands compact RGB333 words into
    a 7-pass true PWM schedule.
  - Added legacy GPIO4 OE mirroring: `GPIO_OE_LEGACY=4`,
    `PIN_OE_ALL=(GPIO18|GPIO4)`, GPIO4 pin configuration, and paired OE
    set/clear in scanner control paths.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_run_candidate.sh`
  - Added `rp1_gpio_e=24`.
  - Added E pad override env vars.
  - Added GPIO24 to the address pad group.
  - Added `rgb333cache-refillplane-fastpad-rowloop-frame7-dwell{16,24,88,96}-...`
    candidates.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_cycle_state32.c`
  - Added `GPIO_E` / `PIN_E` to live state32 cycling.
  - Added legacy GPIO4 to `PIN_OE` so live updates keep GPIO4 and GPIO18 in
    the same OE state.
  - Added `RP1_HUB75_CYCLE_STYLE=psychedelic`.
  - Current palette is deliberately saturated: red, magenta, blue, cyan,
    green, yellow, red, magenta. It avoids white because white made the scene
    look washed out on the physical panel.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_seed_rgb333_words.c`
  - Seeds compact true-PWM RGB333 row-pair words.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_cycle_rgb333.c`
  - Live-updates compact RGB333 frames with a high-saturation moving HSV/ripple
    pattern.
  - Added `RP1_HUB75_RGB333_COLOR_PROFILE=gamma22|cie1931|linear`.
    `gamma22` is now the default visual profile. `cie1931` is a closer
    thresholded approximation of hzeller's default luminance curve, but still
    quantizes down to RGB333.
  - Added `RP1_HUB75_RGB333_VALUE_FLOOR`; the default psychedelic value floor
    is now `220` to keep the panel bright while the profile pulls intermediate
    mixed channels down for cleaner saturation.
  - Added `RP1_HUB75_RGB333_STYLE=rgb-ramp` with
    `RP1_HUB75_RGB333_RAMP_SECONDS=10` support for full-panel red, green, then
    blue brightness ramps.
  - The RGB ramp was returned to uniform no-dither output after the dithered
    version looked like adjacent pixels loading at different brightnesses.
- `tools/testing/selftests/drivers/rp1-pio/rp1_core1_rgb444cache_refillplane_fastpad_rowloop_frame15_dwell88_rgbonly_addr2slow_clk2slow_latoe2slow_lat2_addrnop8_rgbsetclr_preclk1.s`
  - True RGB444 PWM wrapper: 16 per-channel levels, no spatial dithering.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_seed_rgb444_words.c`
  - Seeds compact RGB444 row-pair words.
- `tools/testing/selftests/drivers/rp1-pio/rp1_hub75_cycle_rgb444.c`
  - Runs full-panel red, green, then blue brightness ramps with real 4-bit PWM
    levels on every LED.
- `tools/testing/selftests/drivers/rp1-pio/rp1_core1_rgb333cache_refillplane_fastpad_rowloop_frame7_dwell{16,24,88,96}_rgbonly_addr2slow_clk2slow_latoe2slow_lat2_addrnop8_rgbsetclr_preclk1.s`
  - Wrapper candidates for true 3-bit-per-channel PWM.

## Current Best Visual Command

This is the current best true-PWM visual command. It uses compact RGB333
content, expands it on RP1 into a 7-pass weighted PWM schedule, and rewrites the
shared frame buffer around 120 Hz with the 8 ms updater interval below. `dwell88`
is the best measured balance so far: much brighter than the first RGB333 pass,
but still over the aggregate 1200 fps target.

```sh
cd /home/michael/rp1-pio

./rp1_core1_build_payloads.sh \
  rp1_core1_rgb333cache_refillplane_fastpad_rowloop_frame7_dwell88_rgbonly_addr2slow_clk2slow_latoe2slow_lat2_addrnop8_rgbsetclr_preclk1.s

rm -f /tmp/rp1_hub75_rgb333_dwell88.log
(
  ./rp1_hub75_run_candidate.sh \
    rgb333cache-refillplane-fastpad-rowloop-frame7-dwell88-rgbonly-addr2slow-clk2slow-latoe2slow-lat2-addrnop8-rgbsetclr-preclk1 \
    35 > /tmp/rp1_hub75_rgb333_dwell88.log 2>&1 &
  runner=$!

  sleep 1
  sudo env \
    RP1_HUB75_RGB333_STYLE=psychedelic \
    RP1_HUB75_RGB333_COLOR_PROFILE=gamma22 \
    RP1_HUB75_RGB333_VALUE_FLOOR=220 \
    ./rp1_hub75_cycle_rgb333 0xc000 28 8

  wait "$runner"
  tail -n 10 /tmp/rp1_hub75_rgb333_dwell88.log
)
```

Latest observed result:

```text
cycled-rgb333 updates=1731 seconds=28.000 interval_ms=16
per_panel_fps=302.370 aggregate_fps=1209.481 target_aggregate=1200.000 verdict=PASS
```

Latest `gamma22` color-profile validation on `totem1`:

```text
cycled-rgb333 updates=5397 seconds=45.000 interval_ms=8 style=psychedelic color_profile=gamma22 value_floor=220
per_panel_fps=302.036 aggregate_fps=1208.146 target_aggregate=1200.000 verdict=PASS
```

`dwell96` also ran and may be useful visually, but measured just below the
script target:

```text
per_panel_fps=299.913 aggregate_fps=1199.652 target_aggregate=1200.000 verdict=MISS
```

## Other Useful Commands

Sync local selftests to `totem4`:

```sh
rsync -az \
  /Users/lampe/code/linux/tools/testing/selftests/drivers/rp1-pio/ \
  michael@totem4.local:/home/michael/rp1-pio/
```

Build the currently edited helpers on `totem4`:

```sh
cd /home/michael/rp1-pio
gcc -O2 -Wall -Wextra rp1_hub75_seed_state32.c -o rp1_hub75_seed_state32
gcc -O2 -Wall -Wextra rp1_hub75_cycle_state32.c -o rp1_hub75_cycle_state32
gcc -O2 -Wall -Wextra rp1_hub75_seed_rgb333_words.c -o rp1_hub75_seed_rgb333_words
gcc -O2 -Wall -Wextra rp1_hub75_cycle_rgb333.c -o rp1_hub75_cycle_rgb333
```

Run the original stable solid-red E-pin validation:

```sh
cd /home/michael/rp1-pio
RP1_HUB75_SEED_SOLID=red \
  ./rp1_hub75_run_candidate.sh \
  state32-dsramcache-copy11plane-clkout-addrsetupnop8-seedoe-copydelay5-splithead1-allslow-lat2-clknop-regcount-dwell1 \
  20
```

Check pin mux after a run:

```sh
pinctrl get 24,22,26,27,20,5,12,17,18,21
```

Expected: GPIO24 and the other HUB75 pins should show `PROC_RIO`.

Current OE4 compatibility run left on `totem4`:

```sh
cd /home/michael/rp1-pio
nohup sh -lc '(
  RP1_HUB75_SEED_STATE32_PATTERN=phase \
    ./rp1_hub75_run_candidate.sh \
    state32-dsramcache-copy11plane-clkout-addrsetupnop8-forceoe-lat2-clknop-regcount-dwell16 \
    1800 > /tmp/rp1_hub75_totem4_final.log 2>&1 &
  runner=$!
  sleep 1
  sudo env RP1_HUB75_CYCLE_STYLE=psychedelic \
    ./rp1_hub75_cycle_state32 0xc000 1790 16
  wait "$runner"
)' >/tmp/rp1_hub75_totem4_final.nohup 2>&1 &
```

For this run, `pinctrl get 4,18,24` should show GPIO4, GPIO18, and GPIO24 all
under `PROC_RIO`.

## Validation Already Run

Local validation:

- `cc -O2 -Wall -Wextra -c rp1_hub75_cycle_state32.c`
- `git -C /Users/lampe/code/linux diff --check -- ...`
- `sh -n rp1_hub75_run_candidate.sh`

Remote validation on `totem4`:

- Built `rp1_hub75_seed_state32`.
- Built `rp1_hub75_cycle_state32`.
- Built scanner payloads through `rp1_core1_build_payloads.sh`.
- Ran solid red with E driven:
  - `per_panel_fps=631.306`
  - `aggregate_fps=2525.225`
  - `verdict=PASS`
- Ran psychedelic state32 updates at 16 ms:
  - about `62 Hz` host-side updates
  - scanner around `631 fps` per panel on `dwell1`
- Ran psychedelic state32 updates at 8 ms:
  - about `123 Hz` host-side updates
  - scanner around `631 fps` per panel on `dwell1`
- Ran brighter `dwell8`:
  - scanner around `591 fps` per panel
  - `verdict=PASS`
- Ran brighter `dwell16`:
  - scanner around `576 fps` per panel
  - `verdict=PASS`
- Added and ran true RGB333 PWM:
  - `dwell16`: `per_panel_fps=326.227`, `aggregate_fps=1304.909`, `PASS`
  - `dwell24`: `per_panel_fps=323.399`, `aggregate_fps=1293.595`, `PASS`
  - `dwell96`: `per_panel_fps=299.913`, `aggregate_fps=1199.652`, `MISS`
  - `dwell88`: `per_panel_fps=302.370`, `aggregate_fps=1209.481`, `PASS`
  - Live RGB333 animation updates stayed around `62 Hz`.
- Added GPIO4 legacy-OE mirroring to the active state32 selftest path.
  - Synced `/Users/lampe/code/linux/tools/testing/selftests/drivers/rp1-pio/`
    to `/home/michael/rp1-pio/` on `totem4`.
  - Rebuilt the state32 scanner payload plus `rp1_hub75_seed_state32` and
    `rp1_hub75_cycle_state32`.
  - Launched a short `RP1_HUB75_SEED_SOLID=red` smoke test; log showed payload
    start, seed, and `START_MAGIC` poke.
  - Relaunched the psychedelic state32 updater at 16 ms. Logs reached
    `cycle=720` during validation, and process list showed the scanner and
    updater still running.
  - `pinctrl get` during the run showed GPIO4 as `PROC_RIO04`, GPIO18 as
    `PROC_RIO018`, and GPIO24 as `PROC_RIO024`.
- Added and ran the RGB333 simple color ramp on `totem4`.
  - Local check: `git -C /Users/lampe/code/linux diff --check -- .../rp1_hub75_cycle_rgb333.c`
  - Remote build: rebuilt `rp1_core1_rgb333cache_refillplane_fastpad_rowloop_frame7_dwell88...`
    plus `rp1_hub75_seed_rgb333_words` and `rp1_hub75_cycle_rgb333`.
  - Run command used `RP1_HUB75_RGB333_STYLE=rgb-ramp` and
    `RP1_HUB75_RGB333_RAMP_SECONDS=10` for 30 seconds total: red ramp, green
    ramp, blue ramp.
  - Reran after smoothing with an 8 ms updater interval:
    `./rp1_hub75_cycle_rgb333 0xc000 30 8`.
  - Later removed the smoothing/dither path and returned to no-dither RGB333:
    `sudo env RP1_HUB75_RGB333_STYLE=rgb-ramp RP1_HUB75_RGB333_RAMP_SECONDS=10 ./rp1_hub75_cycle_rgb333 0xc000 590 8`.
- Added and ran a no-dither RGB444 ramp on `totem4`.
  - Local checks: `git -C /Users/lampe/code/linux diff --check -- ...`,
    `sh -n rp1_hub75_run_candidate.sh`, and local `cc -O2 -Wall -Wextra -c`
    for the RGB444 seed/cycle helpers.
  - Remote build: built
    `rp1_core1_rgb444cache_refillplane_fastpad_rowloop_frame15_dwell88...`,
    `rp1_hub75_seed_rgb444_words`, and `rp1_hub75_cycle_rgb444`.
  - Run command:
    `sudo env RP1_HUB75_RGB444_RAMP_SECONDS=10 ./rp1_hub75_cycle_rgb444 0xc000 30 8`.
  - This uses 16 real PWM levels per channel per LED. It intentionally does
    not use adjacent-pixel dithering.
  - User observed the first 30s one-shot in a bad final state: mostly blue with
    a few missing pixels and one shifting row near row 0. Treat RGB444 as
    experimental, not promoted.
  - A longer 600s scanner / 590s updater run was started afterward to avoid the
    stale single-row state that happens when the scanner exits while the panel
    is still connected:
    `sudo env RP1_HUB75_RGB444_RAMP_SECONDS=10 ./rp1_hub75_cycle_rgb444 0xc000 590 8`.
- Added and ran the RGB333 color-profile update on `totem1`.
  - Local check: `cc -O2 -Wall -Wextra -c .../rp1_hub75_cycle_rgb333.c`.
  - Remote build on `totem1`: `gcc -O2 -Wall -Wextra -o rp1_hub75_cycle_rgb333 rp1_hub75_cycle_rgb333.c`.
  - Run command used `RP1_HUB75_RGB333_COLOR_PROFILE=gamma22` and
    `RP1_HUB75_RGB333_VALUE_FLOOR=220`.
  - Scanner result: `per_panel_fps=302.036`, `aggregate_fps=1208.146`,
    `verdict=PASS`.

## Current Interpretation

The earlier row banding was consistent with the E line not being driven. The
panel now looks good after driving GPIO24 as row address E. The display path is
fast enough for animation: the state32 scanner is hundreds of Hz per panel, and
the host-side pattern writer can update the live frame buffer at roughly
60-120 Hz.

There is now a true multi-bit PWM path, but it is not PWM11. RGB333 stores
3 bits per R/G/B channel for both upper and lower pixels in each row-pair word.
RP1 expands it into a 7-pass repeated bit schedule: bit0 once, bit1 twice, bit2
four times. This gives 512 possible colors per pixel instead of the previous
8-color RGB111 mode. Hzeller-style PWM11 color would need a higher-depth source
format or a different compact expander.

Latest Pi5/RP1 tuning update:

- A Pi4-oriented GPIO strategy is the wrong model for this path. Pi4 needs
  slower two-step set/clear GPIO sequencing and tends to settle around
  1-1.5 MHz stable HUB75 clocks. Pi5/RP1 should use direct/full-word RIO output
  where possible, because it can force the output word instead of only OR/clear
  individual bits.
- Pi5 RIO-specific tuning facts now being used:
  - Peripheral base is `0x1f00000000`; GPIO control/RIO/pad-control offsets are
    `0xd0000`, `0xe0000`, and `0xf0000`.
  - GPIO function `0x05` selects RIO control.
  - RIO aliases are normal, XOR at `+0x1000`, SET at `+0x2000`, and CLR at
    `+0x3000`.
  - Pad drive is bits `5:4`; fast slew is bit `0`.
  - A tight RIO XOR loop can produce roughly `25 ns` pulses without explicit
    memory barriers, so dynamic-scene slowdown should be treated as a
    memory/source-expansion problem before a GPIO-speed problem.
- Added an experimental direct-output RGB888 row-major worker:
  `rgb888cache-rowmajor-outfast-frame8-dwell4-warm16-addr2slow-clkfast-latoe2slow-lat2-addrnop4-preclk0`.
  It uses full `RIO_OUT` pixel words, fast CLK pad slew, and a shorter
  address-stage guard.
- On `totem1`, the outfast red-bit-stripe Saleae capture was electrically valid
  enough for parity inspection and the scanner reported about `7238` per-panel
  FPS when the source frame was static.
- On `totem4`, the same outfast worker reported about `7080` per-panel FPS with
  no active host writer touching the source buffer.
- With the animated `sun_64x64.rgb` player writing RGB888 frames every 30 ms,
  `totem4` dropped to about `214` per-panel FPS. That means the current limiter
  is not GPIO edge timing; it is the RP1 worker repeatedly re-reading and
  re-expanding shared-SRAM RGB888 source data while the host is publishing
  frames.
- The next full-color direction is therefore to consume kernel-prepacked
  row-major bitplanes/state32, not to add more GPIO settle padding to the
  RGB888 source expander.

The latest blank-panel suspicion on `totem4` is an OE pinout mismatch: the
scanner sequenced GPIO18, while the physical HUB75 adapter may listen to GPIO4.
The current experimental fix mirrors OE onto GPIO4 in the state32 path. Confirm
the physical panel before promoting this beyond the selftest path or applying
the same compatibility behavior to the kernel worker.

## Next Good Experiments

- Ask Michael how the true RGB333 `dwell88` scene looked on the physical panel.
- If it is stable and brightness matters more than the script target,
  test/consider `dwell96`, which was only barely below target.
- If it needs a cleaner gradient, improve `rp1_hub75_cycle_rgb333.c`; the scan
  path now supports real per-channel levels.
- If 3 bits per channel is not enough, the next bigger step is RGB444 or a more
  efficient bitplane scanner, but that will require more shared memory or a
  different compact format/expander.
- For RGB888/PWM-depth work, prioritize the kernel row-major/CIE-prepacked
  state32 path. Avoid tuning by adding Pi4-style slowdown or long settle NOPs
  unless a Saleae capture shows an actual receiver timing violation.
- Keep `/dev/rp1-hub75` testing separate. Do not expect it to produce GPIO
  output until the kernel worker path actually drives pins.
