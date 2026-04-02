# Pi 5 Scan Transport Layers

This note describes the experimental native Pi 5 scan path and the parity tooling
around it. Piomatter is no longer wired into the app runtime; in this repo it
exists only as an external parity and benchmark reference.

## Problem

The Pi 5 HUB75 parity work now spans two active layers:

- Rust packer/simulator code that turns RGBA into a compact scan-program stream
- external Piomatter checkout tooling used for parity and benchmark runs

The native `/dev/pio0` userspace transport is no longer part of the live app
path, but the packed protocol and simulator still matter because they are the
parity harness for any future clean-room reimplementation work.

## Materials

- [`rust/heart_rgb_matrix_driver/src/runtime/pi5_scan.rs`](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_scan.rs)
- [`src/heart/device/rgb_display/runtime.py`](/Users/lampe/.codex/worktrees/b4c5/heart/src/heart/device/rgb_display/runtime.py)
- [`scripts/prepare_piomatter_parity_checkout.py`](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/prepare_piomatter_parity_checkout.py)

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

### External Piomatter parity path

The repo still carries Piomatter parity tooling for Pi 5 bring-up:

- it patches an external Piomatter checkout
- it preserves a known-good reference transport during parity experiments
- it never becomes part of the production Python runtime surface

The transport ladder is therefore:

1. prove behavior in Piomatter
1. model the equivalent protocol in the Rust simulator/audit stack
1. only then consider another clean-room transport implementation

## Operational Invariants

Two invariants are worth stating explicitly because they explain most of the
driver code:

1. `LOAD` replaces the entire resident payload.
   The transport does not support partial patching of the active frame.
   Callers must rebuild and submit a whole new packed byte stream. That keeps
   replay accounting and ownership rules simple.

1. Presentation counting is transport completion, not panel-photon accounting.
   `WAIT` advances when the transport-specific completion point says a replay
   batch has been consumed. That is intentionally conservative and
   transport-oriented; it avoids userspace inventing its own refresh counter.

Those invariants are why the code prefers coherent buffers, one replay worker
per session, and a narrow ioctl surface over a richer but harder-to-audit
feature set.

## Why The Protocol Stays Shared

Keeping Piomatter parity work and the Rust packer/simulator on the same logical
protocol is intentional:

- correctness fixes land once at the protocol level
- sparse-payload optimizations in Rust remain measurable
- panel behavior stays comparable across the fallback and any future clean-room path
