# Heart RP1 HUB75 Linux Bundle

This directory is the Heart-owned source of truth for the Linux-side RP1 HUB75
bring-up artifacts. The reproducible totem path builds and deploys directly
from this tree.

## Contents

- `files/`: paths laid out like the upstream Linux tree for reviewability.
- `manifest.json`: the explicit file list and RP1 boot preflight words used by
  the helper script.
- `heart.utilities.hub75_lab._bundle`: authoritative bundle deployment logic.
- `scripts/rp1_hub75_linux_bundle.py`: thin compatibility CLI.

## Workflow

1. Edit the files in this bundle.
2. Reproduce the known-good blue totem path from the Heart checkout:

   ```sh
   scripts/rp1_hub75_reproduce_totem_blue.sh michael@totem3.local
   ```

3. Before a visual run, classify the target RP1 firmware state when needed:

   ```sh
   ./scripts/hub75_experiment.py bundle preflight \
     --host totem3.local --remote-dir /home/michael/rp1-pio
   ```

See [`docs/HUB75_LAB.md`](../../docs/HUB75_LAB.md#linux-bundle-commands) for
the exact `list`, `apply`, `diff`, `deploy-target`, and `preflight` matrix.

## Boot Contract

The current scanner launcher depends on a firmware-mediated core1 wake path.
That is intentionally treated as a preflighted boot contract, not an assumption:

- `/dev/rp1-hub75` must exist after `rp1-hub75.ko` is loaded.
- `rp1_sram_read32` must be present on the target.
- The RP1 firmware hook words must match a known launchable layout before the
  legacy launcher is trusted.

If the hook words do not match, do not patch SRAM live during a visual run.
Classify the boot as unsupported for the legacy launcher and fall back to
hzeller or a future kernel-owned worker path.
