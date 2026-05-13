# Heart Agent Instructions

## Import Style
- Never place imports inside functions or methods. Keep imports at module scope so dependencies are visible and stable.

## Testing Philosophy
- Do not introduce broad ad hoc test doubles such as `class _StubPeripheralManager:`. If code needs a manager in tests, prefer constructing a real `PeripheralManager` with explicit configuration, or extract a narrow protocol/helper API that can be tested directly with focused fakes.
- Keep test doubles scoped to the actual collaborator contract under test. Avoid stubbing large coordinator objects just to satisfy incidental attributes; that is a signal the production code needs a smaller dependency boundary.

## Recurring Bench Issues
- Saleae Logic2 capture can fail with `Cannot switch sessions while recording`. Before capture-based HUB75 validation, stop or close the active Logic2 recording session so connector-driven captures can start cleanly.
- Repo-local Saleae capture preflight can fail when the selected interpreter lacks the `saleae` package or no local Logic app is installed. Run preflight before trusting a dead CSV, and use whole-capture diagnostics to separate a silent export from a bad channel map.
- If a same-day Logic2 capture of a known-good PIO run and a slow manual GPIO toggle both export only two static rows, treat the problem as probe/analyzer routing or fixture grounding first. Do not spend more time tuning the kernel until a deliberate channel-identification test shows at least one observed edge.
