# Pi 5 Scan Transport Layers

## Problem

The Pi 5 HUB75 path now spans three layers:

- Rust packer code that turns RGBA into a compact scan-program stream
- a raw rp1-pio userspace transport
- a kernel resident-loop transport

Those layers intentionally share one packed protocol and one PIO parser. Without
an explicit note, future maintainers are forced to reverse-engineer the format
from scattered comments and benchmark history.

## Materials

- [`rust/heart_rust/src/runtime/pi5_scan.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/src/runtime/pi5_scan.rs)
- [`rust/heart_rust/native/pi5_pio_scan_shim.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/native/pi5_pio_scan_shim.c)
- [`rust/heart_rust/native/pi5_scan_loop_shim.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/native/pi5_scan_loop_shim.c)
- [`rust/heart_rust/native/pi5_scan_loop_ioctl.h`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/native/pi5_scan_loop_ioctl.h)
- [`rust/heart_rust/kernel/pi5_scan_loop/heart_pi5_scan_loop.c`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rust/kernel/pi5_scan_loop/heart_pi5_scan_loop.c)

## Packed Protocol

Each row-pair / bitplane group is emitted as:

1. one row-addressed blank word
1. zero or more spans
1. an end-of-spans marker
1. one dwell trailer word

Span encoding is:

- `raw control word`: one-word raw span header
  - bit `0` = raw opcode
  - bits `1..8` = `raw_len - 1`
  - bits `9..31` = first 23-bit GPIO word
  - densely packed 23-bit GPIO words for the remaining columns follow
- `repeat control word`: one-word repeat span
  - bit `0` = repeat opcode
  - bits `1..8` = `repeat_len - 1`
  - bits `9..31` = repeated 23-bit GPIO word
- `0`: end of spans

The packed payload is a dense stream of 23-bit GPIO words. The word width is 23
because the active Adafruit bonnet wiring only uses GPIO `5..27`, so the host
can rebase the sparse GPIO map before transport.

## Layer Responsibilities

### Rust packer

The Rust side owns all payload reduction:

- blank-group elision
- prefix/suffix blank trimming
- large internal blank-gap splitting
- identical-bitplane merging
- repeated-pin-word spans
- dense 23-bit packing

The Rust layer does not try to pace replay. It only decides what bytes the
transport must carry.

### Raw rp1-pio transport

The userspace C shim is the baseline transport:

- load the shared 25-instruction parser
- configure rp1-pio transfer buffers
- submit one packed frame with one ioctl
- wait for TX drain with one ioctl

This path is useful because its behavior is easy to compare against the kernel
resident loop without involving a second packed format.

### Kernel resident loop

The kernel module keeps one packed frame resident in coherent memory and replays
that exact buffer from a kthread:

- `INIT`: allocate resident storage and configure the shared parser
  The current parser keeps the span format intact but generates `LAT` and the
  active `OE` window internally so the packed trailer only carries a dwell word.
- `LOAD`: copy a new packed frame into resident storage
- `START`: begin replay and reset presentation counting
- `WAIT` / `STATS`: expose kernel-owned replay counts
- `STOP`: stop replay

The resident loop does not repack or reinterpret the frame. It only optimizes
how the already-packed bytes reach the RP1 FIFO.

## Operational Invariants

Two invariants are worth stating explicitly because they explain most of the
driver code:

1. `LOAD` replaces the entire resident payload.
   The kernel module does not support partial patching of the resident frame.
   Callers must `STOP`, `LOAD` a whole new packed byte stream, then `START`
   again. That keeps replay accounting and ownership rules simple.

1. Presentation counting is transport completion, not panel-photon accounting.
   `WAIT` and `STATS` advance when the transport-specific completion point says
   a replay batch has been consumed:
   the raw transport uses TX drain, and the resident loop uses MMIO writes plus
   drain. That is intentionally conservative and transport-oriented; it avoids
   userspace inventing its own refresh counter.

Those invariants are why the code prefers coherent buffers, one replay worker
per session, and a narrow ioctl surface over a richer but harder-to-audit
feature set.

## Why The Parsers Match

Keeping the raw rp1-pio transport and the kernel resident loop on the same PIO
program is intentional:

- benchmark differences stay attributable to transport changes
- correctness fixes land once at the protocol level
- sparse-payload optimizations in Rust benefit both paths immediately

If a future change requires a protocol break, it should be treated as a shared
format migration, not a one-off tweak in only one C transport.
