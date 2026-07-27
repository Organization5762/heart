# Experimental reachability inventory

This inventory records the deletion boundary from Heart main
`eb557628eaefb78c5da5b419f713b658701ed433`. It treats every dynamically
discovered program configuration, every peripheral configuration, the three
declared command contracts, and repository scripts as supported roots.

## Method

`ConfigurationRegistry` imports every Python module under
`src/heart/programs/configurations`, so all 42 configuration modules are
supported even when they are not the current totem default. The reachability
audit also includes:

- all modules under `src/heart/peripheral/configurations`;
- the importable `totem` and `heart-state-review` entrypoint modules;
- internal imports made by repository Python scripts;
- the `heart`, `heart.renderers`, `heart.navigation`, and `heart.runtime`
  facades.

A static Python import closure over 429 Heart modules reached 383 modules. Only
three renderer packages were outside that closure. Repository-wide searches
then checked their package names and exported class names across source,
configurations, CLIs, scripts, tests, documentation, deployment files, and
package metadata.

The remaining `flowtoy_spectrum` search hit in `AGENTS.md` is a dated validation
record stating that an earlier change left the package untouched. It is not a
current configuration, entrypoint, or documentation contract.

## Classification

| Area | Classification | Evidence and decision |
| --- | --- | --- |
| `heart.renderers.doppler` | Deletable experiment | No configured mode, CLI, facade export, documentation, script, deployment path, test, or caller outside its own package. Deleted with 220 production lines. |
| `heart.renderers.flowtoy_spectrum` | Deletable experiment | No production or operational caller outside its own package. Its only external consumer was its renderer-specific test. Deleted with 286 production lines and that test. The independent FlowToy peripheral, bridge driver, firmware, and peripheral tests remain supported. |
| `heart.renderers.led_wave_boat` | Deletable experiment | No configured mode, CLI, facade export, documentation, script, deployment path, test, or caller outside its own package. Deleted with 357 production lines. |
| Current program configurations | Supported/configured | All 42 modules are dynamically imported by `ConfigurationRegistry`. Active 2026 scenes and earlier selectable configurations remain unchanged. |
| `totem_debug` entrypoint | Supported but broken on the base commit | `pyproject.toml` and the README declare the hardware-diagnostics CLI, but its configured `heart.x.cli` module does not exist. Preserve the contract pending a separate restoration or retirement decision; it could not contribute an importable module to the static closure. |
| `experimental/` | Supported tooling | The README documents the tree, Beats defaults to `experimental/beats`, CLI tests cover that path, and `scripts/devex_session.py` resolves it. |
| Navigation scene bridge | Supported current runtime | `MultiScene` imports and constructs `native_scene_manager`. Its replacement belongs to the accepted-wheel StateMachine change, not this cleanup. |
| Old ManyFold stream adapters | Reusable current library | `GraphRouteStream`, `runtime_route`, `input/streams.py`, and the observable adapters still have real input, peripheral, runtime, and renderer callers. They remain until accepted replacement APIs exist. |
| Isolated rendering | Supported runtime option | Device selection and environment configuration still select the isolated renderer transport, and tests cover its socket/TCP configuration. |
| RGB-matrix compatibility | Reusable public library | `heart.device.rgb_display` publicly exports the optional compatibility types and focused tests exercise them. The standalone `heart-rgb-matrix-driver` dependency and dumb RGBA submission boundary are preserved. |
| RP1/HUB75 artifacts | Documented hardware reproduction | The known-good totem3 blue reproduction, parameterized HUB75 lab, SRAM map, Linux/kernel/launcher/mailbox bundles, and their tests remain protected. |
| Candidate dependencies | Supported shared dependencies | The deleted renderers use only NumPy, pygame, ManyFold, and standard-library modules. Those dependencies have many supported callers, so this slice removes no dependency. |

## Remaining experimental inventory

The following work remains deliberately outside this deletion slice:

- the process-local scene ownership and optional native scene bridge, pending
  an accepted exact-wheel StateMachine API;
- active Rx-shaped ManyFold adapters and their consumers, pending accepted
  PubSub and processor replacements;
- renderer-local control polling in supported scenes, pending the centralized
  input and scene-machine migrations;
- RGB-matrix compatibility exports, until their public contract is explicitly
  retired;
- documented HUB75 laboratory and recovery assets;
- the supported `experimental/` development and Beats workspaces.

No alias, registry entry, optional import, or compatibility fallback replaces
the deleted renderer packages.

## Baseline validation exceptions

The documented `totem_debug` entrypoint already fails to import
`heart.x.cli` on the recorded base commit. This cleanup preserves the
entrypoint and its README contract; restoring or retiring it requires a
separate decision. Mypy also reports existing ManyFold stream typing failures
in configured packages untouched by this slice. The deleted renderer packages
are outside mypy's configured package set.
