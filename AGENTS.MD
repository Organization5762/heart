# Documentation Guidelines

- If any meaningful changes are made to the runtime architecture or service boundaries, update `docs/code_flow.md`.
- After updating the mermaid source, always regenerate the rendered diagram by running `python scripts/render_code_flow.py --output docs/code_flow.svg` (and include any additional formats you maintain).
- Commit the updated `docs/code_flow.md`, regenerated diagram assets (e.g., `docs/code_flow.svg`), and any script output so the documentation stays accurate.
