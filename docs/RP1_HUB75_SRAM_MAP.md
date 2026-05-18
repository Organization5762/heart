# RP1 HUB75 SRAM Map

This note defines the SRAM boundaries for the RP1 core1 HUB75 selftest path.
Use it before choosing source-frame offsets. Do not pick offsets by trial and
error.

## Address Space

The same shared SRAM has three relevant address views:

| Actor | Base | Notes |
| --- | --- | --- |
| Linux host/AP | `0x1f00400000` | PCIe BAR address used with `/dev/mem` by the selftest helpers. |
| RP1 Cortex-M processors | `0x20000000` | Core-local shared SRAM alias used by assembly payloads. |
| RP1 DMA bus master | `0xc020000000` | 40-bit bus-master view. Verified with `rp1_dma_memcpy_probe`: `/dev/rp1-hub75` DMA slot to `0xc020000000 + 0xc000` produced `status=0x2 bad=0` on `totem1`. |

The host-visible RP1 shared SRAM window used by the selftests is:

| Range | Status | Notes |
| --- | --- | --- |
| `0x20000000..0x20005fff` | Reserved | RP1 firmware/low shared state. Known firmware hook and feature-table addresses live here, including `0x2000012c` and `0x20005928`. |
| `0x20006000..0x20006fff` | Reserved | Live RP1 firmware state has been observed here. On `totem1` on 2026-05-17, `0x20006ba8` changed over time while the HUB75-launched core1 was held in reset. |
| `0x20007000..0x20007fff` | Reserved | Core1 launch stub and launch counter area. `rp1_core1_launch_mem.c` uses `0x20007000` and `0x20007020`. |
| `0x20008000..payload_end` | Reserved | Core1 payload loaded by `rp1_core1_launch_mem.c`. Payload size changes per candidate. |
| `payload_end..0x2000feff` | Candidate data window | Only safe after subtracting the source buffer size and alignment. |
| `0x2000ff00..0x2000ffff` | Reserved | Firmware shared mailbox, `RP1_FW_SHMEM_ADDR`. Do not overlap it. |

Local core1 aliases are separate:

| Range | Status | Notes |
| --- | --- | --- |
| `0x10000000..0x10001fff` | Local ISRAM | Payloads copy hot text here before jumping locally. |
| `0x10002000..0x10003fff` | Local DSRAM/stack | Used for row cache / DSRAM cache. Initial stack is `0x10003ffc`. This is not a host source-frame buffer. |

## Hard Rule

For a shared source buffer:

```text
source_start >= align_up(0x20008000 + payload_bin_size, required_alignment)
source_end   <= 0x2000ff00
source_end   = source_start + source_size
```

Also avoid all reserved ranges above. In particular, `0x2000c000` is only safe
for small payloads. It is not a general-purpose source address.

Do not try to "zero out" the low firmware area to claim more space. The Linux
RP1 firmware driver only documents the mailbox page at `0x2000ff00..0x2000ffff`,
but Raspberry Pi engineers have stated that the RP1 firmware expects access to
the whole shared SRAM window. Treat reclaiming low SRAM as a power-cycle-only
experiment with explicit firmware-version gating, not as a runtime cleanup.

## Live Firmware Evidence

Read-only snapshots on `totem1` on 2026-05-17 used:

```text
sudo ./rp1_sram_dump 0 0x10000
sudo ./rp1_mmio_poke32 0x16000 0x80000000
```

The first command captured the full 64 KiB shared SRAM window. The second held
the launched RP1 core1 in reset before a second pair of dumps. The only word
that continued changing between reset-held snapshots was `0x20006ba8`, which
points to firmware/core0 activity rather than the HUB75 scanner. The documented
firmware mailbox still lives at `0x2000ff00..0x2000ffff` and is used by
`drivers/firmware/rp1-fw.c` through the `rp1_fw_shmem` devicetree node.

## Current Payload Examples

Measured on `totem1` during the 2026-05-16 parity pass:

| Candidate | `.bin` size | Payload range | Resulting safe tail before mailbox |
| --- | ---: | --- | ---: |
| `rgb888cache-refillplane...frame8-dwell4...` | `7,716` bytes (`0x1e24`) | `0x20008000..0x20009e23` | `0x60dc` bytes |
| `rgb888cache-rowmajor...frame8-dwell4...` | `19,720` bytes (`0x4d08`) | `0x20008000..0x2000cd07` | `0x31f8` bytes |

Consequences:

| Buffer size | Safe page-aligned start with 7,716-byte payload | Safe page-aligned start with 19,720-byte payload |
| ---: | --- | --- |
| `16 KiB` (`0x4000`) | `0x2000a000` or `0x2000b000` | None |
| `24 KiB` (`0x6000`) | None on a 4 KiB page boundary; only a tight unaligned tail such as `0x20009f00..0x2000feff` fits | None |
| `90,112` bytes (`0x16000`) | Impossible in the 64 KiB shared SRAM window | Impossible |

`0x2000c000` with a `16 KiB` buffer reaches `0x20010000`, so it overlaps the
firmware mailbox page `0x2000ff00..0x2000ffff`. It has worked in some tests
because the firmware mailbox was not active afterward, but it is not a safe
baseline address.

`0x20004000` is also invalid for source frames: it overlaps firmware/feature
table and launch territory before `0x20008000`.

## Safe Starting Policy

Use these defaults until the driver owns a real allocation scheme:

| Format | Size | Use this only when | Start |
| --- | ---: | --- | --- |
| compact RGB888/RGB333/RGB444 one-frame source | `16 KiB` or less | payload `.bin <= 0x2000` if using `0x2000a000`; payload `.bin <= 0x3000` if using `0x2000b000` | Prefer `0x2000b000` |
| packed RGB111 one-frame source | `24 KiB` | not safe with current payload layout | Do not use yet |
| expanded 11-plane state32 frame | `90,112` bytes | not possible in single RP1 shared SRAM | Do not use |

For the row-major RGB888 experiment, the current payload is too large to leave
a safe `16 KiB` source buffer in shared SRAM. The next implementation should
either shrink the payload below `0x3000`, split source loading, or move to a
kernel-owned/double-buffer allocation instead of choosing another magic offset.

## Source References

- `/Users/lampe/code/linux/tools/testing/selftests/drivers/rp1-pio/rp1_core1_launch_mem.c`
  defines `DEFAULT_LAUNCH_ADDR=0x20007000`,
  `DEFAULT_PAYLOAD_ADDR=0x20008000`,
  `RP1_SHARED_SRAM_END=0x20010000`, and
  `RP1_FW_SHMEM_ADDR=0x2000ff00`.
- `/Users/lampe/code/linux/tools/testing/selftests/drivers/rp1-pio/rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s`
  defines the local aliases `LOCAL_ISRAM=0x10000000` and
  `LOCAL_DSRAM=0x10002000`.
