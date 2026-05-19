# RP1 HUB75 Regular P0/P1 Chain2 Audit Schema

This document defines the current audit contract for the `regular` P0/P1
chain2 path used by the 2x2 totem face.

## Live Config Under Audit

| Layer | Value |
| --- | --- |
| Host | `totem3.local` |
| Device | `/dev/rp1-hub75` |
| Wiring profile | `regular` / `ThreePortActive` |
| Logical frame from Heart/Rust | `256x64` RGB888 strip |
| Logical panels across x | `A B C D`, each `64x64` |
| Kernel config | `cols=64 rows=64 panel_count=4 lane_count=2 chain_length=2` |
| Stream | `state32` |
| PWM bits | `6` |
| Dwell shift limit | `7` |
| Scanner candidate | `state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2-clkretain` |
| Scanner frame rate observed | about `457 Hz` |
| External scanner control slot | `0xb800` |
| Active slot DMA | `0x000000103a65c000` or `0x000000103aa5c000` depending queued slot |

`clkretain` means RGB is cleared independently from CLK, then CLK is explicitly
set high and explicitly cleared low. The baseline scanner without this knob is
`state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2`.

## Driver Output Schema

The driver must provide exactly `49152` bytes:

```text
width  = 256
height = 64
bytes  = width * height * 3
format = RGB888
order  = row-major
```

Pixel byte offset:

```text
offset(x, y, channel) = ((y * 256 + x) * 3) + channel
channel: R=0, G=1, B=2
```

Logical panel ranges:

| Panel | x range | y range | Meaning |
| --- | ---: | ---: | --- |
| `A` | `0..63` | `0..63` | first logical panel |
| `B` | `64..127` | `0..63` | second logical panel |
| `C` | `128..191` | `0..63` | third logical panel |
| `D` | `192..255` | `0..63` | fourth logical panel |

The driver must not pre-stack this into `128x128` for the regular P0/P1 chain2
path. The kernel packer owns the projection into P0/P1 transport lanes.

## Hzeller Regular Pin Contract

The packer and active regular wrapper intentionally match hzeller's `regular`
hardware mapping:

| Signal | GPIO |
| --- | ---: |
| `P0_R1/P0_G1/P0_B1` | `11 / 27 / 7` |
| `P0_R2/P0_G2/P0_B2` | `8 / 9 / 10` |
| `P1_R1/P1_G1/P1_B1` | `12 / 5 / 6` |
| `P1_R2/P1_G2/P1_B2` | `19 / 13 / 20` |
| `CLK/LAT/OE` | `17 / 4 / 18` |
| `A/B/C/D/E` | `22 / 23 / 24 / 25 / 15` |

The RP1 assembly common include does not provide P1 defaults. Any wrapper that
sets `USE_P1_RGB=1` must define all six `GPIO_P1_*` values explicitly.

## Kernel Packer Row/Column Schema

For state32 regular P0/P1 chain2:

```text
row_pairs   = rows / 2 = 32
active_cols = cols * chain_length = 128
input_cols  = active_cols * lane_count = 256
planes      = pwm_bits = 6
```

State32 word order:

```text
for row_pair in 0..31:
  for plane in 0..5:
    for col in 0..127:
      emit one state32 word
```

Word index:

```text
word_index(row_pair, plane, col) =
  ((row_pair * 6 + plane) * 128) + col
```

Source pixels for each emitted word:

```text
P0 top    = pixel(x = col,              y = row_pair)
P0 bottom = pixel(x = col,              y = row_pair + 32)
P1 top    = pixel(x = col + active_cols, y = row_pair)
P1 bottom = pixel(x = col + active_cols, y = row_pair + 32)
```

Thus the transport columns are:

| Transport col range | P0 source | P1 source |
| ---: | --- | --- |
| `0..63` | `A` top/bottom | `C` top/bottom |
| `64..127` | `B` top/bottom | `D` top/bottom |

For a single `row_pair`, the scanner shifts all `128` transport columns for
plane `0`, then all `128` columns for plane `1`, and so on through plane `5`,
before advancing to the next row address.

## Row Address Schema

Each row address selects one top/bottom row pair:

| Row address | Top y | Bottom y |
| ---: | ---: | ---: |
| `0` | `0` | `32` |
| `1` | `1` | `33` |
| `2` | `2` | `34` |
| `...` | `...` | `...` |
| `31` | `31` | `63` |

Address pins encode `row_pair`:

```text
A = bit 0
B = bit 1
C = bit 2
D = bit 3
E = bit 4
```

## Minimal Audit Pattern

Use a `256x64` RGB888 frame with unique content in each logical panel and row
markers that distinguish top from bottom:

| Panel | Base color | Purpose |
| --- | --- | --- |
| `A` | red | P0, first chain segment |
| `B` | green | P0, second chain segment |
| `C` | blue | P1, first chain segment |
| `D` | white | P1, second chain segment |

Expected first-row state32 examples with all color bytes `0xff` for their
panel color:

| Word | Source | Expected active color pins |
| ---: | --- | --- |
| `word[0]` | `A top/bottom + C top/bottom` | `P0_R1 P0_R2 P1_B1 P1_B2` |
| `word[64]` | `B top/bottom + D top/bottom` | `P0_G1 P0_G2 P1_R1 P1_G1 P1_B1 P1_R2 P1_G2 P1_B2` |
| `word[128]` | same as `word[0]`, next plane | same pins for full-intensity colors |

If these words are correct but the cube is visually permuted, the remaining
problem is physical panel order, chain direction, panel orientation, or scanner
clocking, not the driver byte schema.

## Active Scanner Contract

The RP1 scanner consumes pre-packed `state32` words. It should not understand
logical panels, RGB888 bytes, or `A B C D` layout. Those concerns end at the
kernel packer.

| Stage | Responsibility | Active code |
| --- | --- | --- |
| Rust | Produce `256x64` RGB888 bytes in logical `A B C D` order | `Rp1Hub75FrameLoader::Direct` |
| Kernel | Convert RGB888 into `state32[row_pair][plane][col]` words | `rp1h_pack_rgb888_state32()` |
| RP1 scanner | Stream one pre-packed `u32` per clock and handle OE/LAT/address/dwell timing | `STATE32_DMA_PIPELINE4_CHUNK_STREAM_LOOP` plus row/timing macros |

Distilled scanner loop:

```text
wait for a published frame slot
for row_pair in 0..31:
  for plane in 0..pwm_bits:
    copy/prefetch the packed state32 row slice
    for col in 0..127:
      clear RGB/CLK pins
      set RGB pins from state32[col]
      raise CLK
      lower CLK
    blank OE
    pulse LAT
    update row address
    enable OE
    dwell for this plane
```

The GPIO pin defaults and alias checks live in
`rp1_core1_hub75_gpio_pins.inc`. That include is intentionally separate from
the scanner loop so audits can verify the pin contract without reading the
streaming/timing implementation.
