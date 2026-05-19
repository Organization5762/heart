# Heart Agent Instructions

## Import Style
- Never place imports inside functions or methods. Keep imports at module scope so dependencies are visible and stable.

## Testing Philosophy
- Do not introduce broad ad hoc test doubles such as `class _StubPeripheralManager:`. If code needs a manager in tests, prefer constructing a real `PeripheralManager` with explicit configuration, or extract a narrow protocol/helper API that can be tested directly with focused fakes.
- Keep test doubles scoped to the actual collaborator contract under test. Avoid stubbing large coordinator objects just to satisfy incidental attributes; that is a signal the production code needs a smaller dependency boundary.

## Recurring Bench Issues
- For RP1 HUB75 experiments, prefer well-parameterized candidates and runtime/config switches over cloning large assembly or runner blocks for each variant. Keep edits small and reusable so tuning changes do not require broad rewrites.
- No copy-paste forks for actual experiments; one-off prototypes are fine, but promoted experiments should share parameterized code.
- Prefer proving debugging and validation claims with well-formatted comparison tables that include the essential parameters, measurements, and verdicts.
- Label comparison-table metrics with direction hints such as "higher better" or "lower better" when the interpretation is not obvious.
- Saleae Logic2 capture can fail with `Cannot switch sessions while recording`. Before capture-based HUB75 validation, stop or close the active Logic2 recording session so connector-driven captures can start cleanly.
- Repo-local Saleae capture preflight can fail when the selected interpreter lacks the `saleae` package or no local Logic app is installed. Run preflight before trusting a dead CSV, and use whole-capture diagnostics to separate a silent export from a bad channel map.
- If a same-day Logic2 capture of a known-good PIO run and a slow manual GPIO toggle both export only two static rows, treat the problem as probe/analyzer routing or fixture grounding first. Do not spend more time tuning the kernel until a deliberate channel-identification test shows at least one observed edge.
- Before drawing totem-specific conclusions from Saleae captures, prove the probes are attached to the intended host. On 2026-05-12, captures stayed live while only `totem1` scanned and went flat when `totem1` was forced low, even with `totem4` actively running.
- For HUB75 HAT-style wiring, check both OE candidates: GPIO18 and legacy GPIO4. A static GPIO4 output-low is not equivalent to sequencing OE; mirror the blank/active OE waveform when validating the selftest or kernel worker path.
- For HUB75 logic-analyzer comparisons, always report OE active/blank duty alongside clock, latch, address, and color-channel checks. Treat active-low OE duty as a first-class brightness/performance signal.
- For the known-good totem3 blue RP1 HUB75 path, use self-contained Heart artifacts via `scripts/rp1_hub75_reproduce_totem_blue.sh` and `docs/RP1_HUB75_TOTEM_BLUE_REPRO.md`. Do not substitute the Rust color-loop runner when reproducing the 500 Hz state32 scanner.
- For regular P0/P1 chain2 state32 scanner tests, republish a fresh frame slot at `0xb800` before poking `START_MAGIC`; stale slab metadata can leave the worker stuck at `DMCP` with frame counter `0`.
- Do not use temporal PWM for HUB75 brightness experiments. Low-brightness temporal flicker looks bad and can create seizure-like flashing; debug color depth with true bitplanes or static non-temporal patterns instead.
- Before changing RP1 HUB75 shared-SRAM source offsets, check `docs/RP1_HUB75_SRAM_MAP.md`. Do not use `0x2000c000` or `0x20004000` as generic safe buffers; validate against payload size and reserved firmware/launcher/mailbox ranges first.
