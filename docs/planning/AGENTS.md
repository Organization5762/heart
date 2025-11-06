# Planning Docs Style Guide

Planning documents in this directory are technical playbooks. They should read as precise, evidence-driven guides that help another contributor reproduce the same line of reasoning without additional meetings. Emphasise hypotheses, measurable outcomes, and the mechanisms that connect the two. `input_event_bus.md` illustrates the desired level of depth.

## Structure

1. **Opening abstract.** Begin with a concise summary describing the system surface, the outcome under investigation, and the primary users or operators. Include a short "Why now" paragraph that situates the work within current constraints or research questions.
1. **Success criteria table.** Provide a table that lists the target behaviours, the quantitative or observable signal that demonstrates success, and the owner responsible for validation. Phrase each row in neutral, technical language so it stands on its own in design reviews.
1. **Task breakdown checklists.** Divide the work into clearly named phases (for example, "Discovery", "Implementation", "Validation"). Within each phase include a checklist of verifiable steps, the artifacts they produce, and links to related notes or source modules.
1. **Narrative walkthrough.** After the checklists, add a prose section that explains how the phases connect. Highlight expected collaboration points, decision gates, and the rationale for sequencing. The narrative should make it easy to interrogate assumptions during review.
1. **Visual references.** Include at least one diagram or table beyond the success criteria table. Lightweight ASCII diagrams, sequence charts, or comparative tables are preferred. When importing diagrams from external tools, document the source and export format.
1. **Risk analysis.** Dedicate a section to risks, mitigations, and contingency triggers. Present them in a table with columns for probability, impact, mitigation strategy, and early warning signals. Follow with a checklist of mitigation tasks.
1. **Outcome snapshot.** Conclude with a short description of the system once the plan lands. Focus on the measurable signals, operator workflows, and any follow-on experiments it unlocks.

## Tone and formatting

- Write in active voice with short, declarative sentences. Use bold headings for sections and sentence case for checklist items.
- Keep paragraphs compact (2–4 sentences) and interleave them with tables, checklists, and diagrams so the reader can scan quickly.
- Use markdown callouts ("Note", "Tip", "Warning") to surface nuances or dependencies that warrant additional attention.
- Prefer precise technical vocabulary over colloquial phrases. Refer to internal concepts (for example, "signal capture" or "state synchronisation") only when they clarify intent.

## Depth expectations

Plans should land in the 800–1200 word range. Err on the side of documenting assumptions, dependencies, and validation methods so a teammate can reproduce the analysis. Whenever tasks reference code or data, point to concrete modules, dashboards, or experiments.

## Quality checklist for authors

- [ ] Opening abstract captures the objective, the context, and the relevant stakeholders in under five sentences.
- [ ] Success criteria table lists measurable signals and responsible owners.
- [ ] Every phase contains a checklist with actionable, verifiable tasks.
- [ ] Narrative walkthrough ties the phases together and motivates the sequencing.
- [ ] At least one diagram or supplemental table clarifies flow or decision points.
- [ ] Risk analysis includes both tabular assessment and mitigation tasks.
- [ ] Outcome snapshot describes the observable state once the plan ships.
- [ ] Tone remains technical, formal, and oriented around evidence.
- [ ] References to related docs and artifacts are embedded where helpful.
- [ ] Word count lands between 800 and 1200 words.

## Review guidance

Reviewers should interrogate each success criterion and confirm that the plan supplies a clear path to measure it. Trace risks to mitigations and ensure every dependency has an owner. Request revisions whenever rationale is missing or when additional visuals would illuminate the design.
