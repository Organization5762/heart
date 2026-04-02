# Piomatter Custom Program Injection

## Problem

We want to try Heart's assembled Pi 5 `.pio` programs inside Adafruit Piomatter, because Piomatter is the current known-good Pi 5 display path and stock `heart_rgb_matrix_driver` userspace transport is disabled.

Stock Piomatter does not expose a runtime API for "load this assembled PIO program instead of `protomatter`". Its C++ layer hardcodes the `protomatter` instruction array and wrap metadata when calling `pio_add_program(...)`.

## Current Constraints

- Heart's generated `.pio` outputs live in:
  - [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_pio_programs_generated.rs](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/src/runtime/pi5_pio_programs_generated.rs)
- Heart's readable `.pio` sources live in:
  - [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/pi5_simple_hub75.pio](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/pi5_simple_hub75.pio)
  - [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/pi5_resident_parser.pio](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/pi5_resident_parser.pio)
- Piomatter is currently used through:
  - [/Users/lampe/.codex/worktrees/b4c5/heart/scripts/piomatter_rgb_cycle.py](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/piomatter_rgb_cycle.py)
  - [/Users/lampe/.codex/worktrees/b4c5/heart/scripts/prepare_piomatter_parity_checkout.py](/Users/lampe/.codex/worktrees/b4c5/heart/scripts/prepare_piomatter_parity_checkout.py)

## Practical Approach

The shortest path is a small Piomatter fork or local patch:

1. Generate a Piomatter-shaped `.pio.h` header from Heart's `.pio`.
1. Replace Piomatter's `protomatter.pio.h` include or its backing symbols.
1. Keep Piomatter's existing replay/threading/render path unchanged.

This isolates the experiment to one variable:

- Heart program semantics
- Piomatter host transport

## Compatibility Generator

Use:

```bash
./.venv/bin/python rust/heart_rgb_matrix_driver/tools/generate_piomatter_parity_header.py
```

This writes:

- [/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/protomatter.pio.h](/Users/lampe/.codex/worktrees/b4c5/heart/docs/research/generated/piomatter_override/protomatter.pio.h)

By default it assembles:

- [/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_protomatter_parity.pio](/Users/lampe/.codex/worktrees/b4c5/heart/rust/heart_rgb_matrix_driver/pio/piomatter_protomatter_parity.pio)

and emits the symbol names Piomatter expects:

- `protomatter`
- `protomatter_wrap_target`
- `protomatter_wrap`

## Important Caveat

Matching the header shape is not sufficient by itself.

Piomatter's host command stream and our simple command stream are not guaranteed to be identical. So this experiment is only meaningful if the injected program still expects the same streamed word contract that Piomatter sends.

That means the best near-term experiment is:

1. keep Piomatter's host-side buffer format
1. inject only a program that is compatible with that format
1. compare panel behavior

If the program expects a different command stream, Piomatter must also be patched on the host side.

## Checkout Prep

To patch a Piomatter source checkout in-place:

```bash
PYTHONPATH=/home/michael/heart/src python3 scripts/prepare_piomatter_parity_checkout.py \
  --checkout /home/michael/tmp/Adafruit_Blinka_Raspberry_Pi5_Piomatter
```

That regenerates the parity header and replaces:

- `src/include/piomatter/protomatter.pio.h`

inside the target checkout.

## Recommendation

Treat this as a fork experiment, not a runtime configuration feature:

- patch Piomatter locally
- verify one full-screen probe on the panel
- only then decide whether Heart should maintain a permanent compatibility layer
