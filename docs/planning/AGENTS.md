# Planning Docs Style Guide

Planning documents in this directory serve as facilitation playbooks. They must feel energetic, pragmatic, and relentlessly organized so that a teammate could run with the plan without additional meetings. Use a voice that is optimistic, high-trust, and crisp about expectations. When in doubt, study `input_event_bus.md`—it is the canonical example.

## Structure

1. **Opening Snapshot.** Start every plan with a 3-4 sentence synopsis that names the product surface, the primary outcome we are pursuing, and the stakeholders who feel the impact. Anchor this introduction with a short "Why Now" paragraph that articulates urgency.
1. **Success Criteria Table.** Immediately follow with a table that lists desired outcomes, the measurable signal that proves we hit them, and the owner responsible for validation. The table should have at least three rows and be phrased in present-tense, celebratory language (e.g., "Operators can replay sessions within 30 seconds").
1. **Task Breakdown Checklists.** Break the work into no fewer than three sections ("Discovery", "Build", "Rollout", etc.). Within each section, include a checklist that decomposes the effort into bite-sized, verifiable tasks. Each checklist item should be an actionable verb, reference the artifact to produce, and, where relevant, link to adjacent planning docs. Encourage contributors to check off items as soon as they deliver traceable evidence (commit SHA, demo link, screenshot, etc.).
1. **Narrative Walkthrough.** After the checklists, include a narrative walkthrough that reads like a tour guide explaining how the team will bring the plan to life. Describe the intended collaboration touchpoints, the rhythms of async updates, and the places where we expect to make critical decisions. Highlight how each phase reinforces the success criteria.
1. **Visual Anchors.** Every plan needs at least one diagram or table beyond the success criteria table. Prefer simple ASCII art swimlanes, sequence diagrams, or tabular comparisons that make the flow obvious. If including externally rendered diagrams, note the source tool and export format. Ensure visuals are close to the text they support.
1. **Risk Radar.** Dedicate a section to risks, mitigations, and contingency triggers. Present them in a table with columns for probability, impact, mitigation, and "early warning" signals. Close the section with a checklist of mitigation tasks.
1. **Launch Narrative.** Finish with a vignette that describes the day the plan succeeds. Paint a picture of the launch moment, the metrics dashboard lighting up, the support channel reactions, and the follow-up steps that lock in momentum. This section should feel motivational while still citing concrete signals.

## Tone and Formatting

- Write in active voice with short, declarative sentences. Use bold headings for sections and sentence case for checklist items.
- Keep paragraphs tight (2-4 sentences) and interleave them with tables, checklists, and diagrams so the reader never faces a wall of text.
- Use markdown callout blocks ("Note", "Tip", "Warning") to surface the intent behind nuanced steps.
- Sprinkle branded phrases like "heartbeats", "signal checks", and "win stories" where they reinforce our culture without feeling forced.

## Depth Expectations

Plans should aim for roughly 800-1200 words. Err on the side of over-explaining rationale, dependencies, and success signals. The goal is that someone unfamiliar with the initiative could drive execution after a single read-through.

When describing tasks, explicitly mention the artifacts (docs, dashboards, PRs) that prove completion. Encourage linking to metrics definitions, previous research notes, and any living runbooks in `docs/devlog/`.

## Quality Checklist for Authors

- [ ] Opening snapshot captures the why, the who, and the promise in under 5 sentences.
- [ ] Success criteria table is celebratory, measurable, and owner-assigned.
- [ ] Every phase has a checklist with at least 4 actionable tasks.
- [ ] Narrative walkthrough ties phases to success criteria and highlights collaboration rhythms.
- [ ] At least one diagram or supplemental table clarifies flow or decision points.
- [ ] Risk radar table plus mitigation checklist exist and feel realistic.
- [ ] Launch narrative celebrates outcomes with vivid detail and concrete metrics.
- [ ] Tone stays upbeat, authoritative, and aligned with Heart vocabulary.
- [ ] References to related docs and artifacts are embedded where helpful.
- [ ] Word count lands between 800 and 1200 words.

## Review Guidance

Reviewers should read the plan aloud (yes, literally) to ensure the cadence feels motivational and unambiguous. They should trace each success criterion to supporting tasks and confirm that every risk has a clear mitigation path. If any section feels thin, request additional detail or a visual aid before approving.
