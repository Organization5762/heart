# Markdown Style Guide

This guide outlines the preferred conventions for writing Markdown documents in the `docs/` directory. It focuses on producing consistent, scannable documentation that renders cleanly on GitHub.

## Use Descriptive Titles and Headings

- Use `#` for the document title and start with a concise, action-oriented phrase (for example, `# Configure the Sensor Driver`).
- Use heading levels in order (`##`, `###`, `####`) to create a clear outline. Avoid skipping levels.
- Keep headings brief—prefer noun phrases or imperative verbs that make scanning easy.
- When adding long-form guidance, insert a short introductory paragraph before the first secondary heading to summarize the page.

## Provide Structured Navigation

- Use a table of contents for documents longer than a few screens. Link each entry to the relevant section using fragment identifiers, for example: `- [Calibrate the Magnetometer](#calibrate-the-magnetometer)`.
- When referencing a section elsewhere in the document, repeat the fragment link inline: `See [Calibrate the Magnetometer](#calibrate-the-magnetometer) for details.`
- Keep anchor text descriptive. Avoid "click here" in favor of phrases like `See [Diagnostics Workflow](#diagnostics-workflow)`.

## Write Focused Paragraphs and Lists

- Favor short paragraphs (2–4 sentences) that cover a single idea.
- Use bullet lists to enumerate related items or prerequisites. Use numbered lists for sequences of steps that must be followed in order.
- Introduce each list with a lead-in sentence ending in a colon.
- Indent nested lists by two spaces to keep GitHub rendering aligned.

## Call Out Key Syntax Elements

- Use fenced code blocks with a language identifier for command-line or code snippets, for example:
  
  ```bash
  make format
  ```
- Use inline code (`` `like this` ``) to highlight filenames, commands, or configuration keys.
- Bold important warnings or decision points. Reserve italics for emphasis or terminology being defined.

## Organize Tabular and Supplementary Information

- Use tables to compare options, list configuration flags, or present structured data. Keep header labels short and align text using standard GitHub table syntax.
- Collapse long examples or reference material with details using HTML `<details>` blocks to keep main narratives concise.
- Reference external assets (images, diagrams) with descriptive alt text: `![Flight controller diagram](./images/flight-controller.png)`.

## Leverage GitHub Markdown Features

- Use automatic section links to create contextual shortcuts, such as `Link to the helpful section: [Θ Tuning](#theta-tuning)`.
- Include task lists (`- [ ]`) when tracking outstanding work items or checklists.
- Apply callouts by combining bold text with emojis when highlighting alerts, for example: `**⚠️ Warning:** Always disconnect power before servicing hardware.`
- Add footnotes for supplemental detail that would otherwise interrupt the main flow. Define them at the bottom of the document.

## Maintain Cross-References and Context

- When referencing code, cite the module path or script name explicitly, e.g., `See \`src/drivers/imu.py\``.
- Link to related documents within the repository using relative paths so navigation works from any branch, for example: `[Driver bring-up checklist](./planning/driver_bringup.md)`.
- Provide a short "Further reading" section at the end of long-form guides to aggregate related resources.

## Review Before Publishing

- Run `make format` to apply mdformat and keep spacing consistent.
- Preview the rendered Markdown locally (e.g., via a Markdown viewer or GitHub web preview) to verify tables, code blocks, and anchors render correctly.
- Confirm that all section links resolve, code blocks have language hints, and lists render as expected.
