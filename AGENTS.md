# Heart Agent Instructions

- Keep this file limited to durable, repository-specific rules and formulas. Never record active work, validation history, incident logs, branch or PR state, or machine-specific observations.
- Keep imports at module scope; never import inside functions or methods.
- In tests, prefer real configured collaborators. When isolation is necessary, extract a narrow protocol or helper and fake only that contract; do not stub broad managers or coordinators.
- Parameterize RP1 HUB75 experiments with shared code and runtime or configuration switches; do not promote copy-paste experiment forks.
- Never use temporal PWM for HUB75 brightness. Use true bitplanes or static patterns, and consult `docs/RP1_HUB75_SRAM_MAP.md` before changing shared-SRAM offsets.
- When syncing to a totem, exclude `.git/`, `.worktrees/`, `.uv-cache/`, `.venv/`, `.captures/`, `tmp/`, `target/`, `node_modules/`, and `__pycache__/`.
- Schedule expensive frame-tick renderer state work through the bounded, priority-aware background stream scheduler, not inline on the main loop.
