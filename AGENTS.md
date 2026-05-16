# Heart Agent Instructions

## Import Style
- Never place imports inside functions or methods. Keep imports at module scope so dependencies are visible and stable.

## Testing Philosophy
- Do not introduce broad ad hoc test doubles such as `class _StubPeripheralManager:`. If code needs a manager in tests, prefer constructing a real `PeripheralManager` with explicit configuration, or extract a narrow protocol/helper API that can be tested directly with focused fakes.
- Keep test doubles scoped to the actual collaborator contract under test. Avoid stubbing large coordinator objects just to satisfy incidental attributes; that is a signal the production code needs a smaller dependency boundary.
