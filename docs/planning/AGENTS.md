# Planning Docs Style Guide

Planning documents in this directory must function as technical playbooks. They should open with an explicit problem statement and a materials list so contributors know the context and required resources before diving into the plan. Keep the tone precise and engineering-focused—avoid marketing language entirely.

## Structure

1. **Problem Statement.** Begin with a short section describing the technical problem in plain language.
1. **Materials.** List the hardware, software, and data prerequisites.
1. **Opening abstract.** Summarise the proposal, why it is needed now, and the intended outcomes.
1. **Success criteria table.** Capture target behaviours, validation signals, and owners in tabular form.
1. **Task breakdown checklists.** Divide the work into phases (for example, Discovery, Implementation, Validation) with checkbox items that can be executed independently.
1. **Narrative walkthrough.** Explain how the phases connect and highlight critical dependencies or decision gates.
1. **Visual reference.** Include at least one diagram or table clarifying flow, data contracts, or component boundaries.
1. **Risk analysis.** Provide a table covering probability, impact, mitigations, and early warning signals. Follow with a mitigation checklist.
1. **Outcome snapshot.** Describe the observable system state once the plan lands.

## Tone and Formatting

- Write in active voice with concise sentences. Prioritise technical vocabulary and avoid superlatives or marketing framing.
- Keep paragraphs short (2–4 sentences) and interleave them with tables, checklists, or diagrams to support scanning.
- Use markdown callouts only when they emphasise nuanced implementation details.
- Reference code modules, scripts, and data sources explicitly so implementers can locate them quickly.

## Depth Expectations

Plans should land in the 800–1200 word range when the problem warrants it. Err on the side of documenting assumptions, dependencies, and validation methods so a teammate can reproduce the analysis. When tasks reference code or data, point to concrete modules, dashboards, or experiments.

## Quality Checklist for Authors

- [ ] Problem statement clearly articulates the technical gap.
- [ ] Materials list enumerates prerequisites.
- [ ] Success criteria table lists measurable signals and responsible owners.
- [ ] Every phase contains a checklist with actionable, verifiable tasks.
- [ ] Narrative walkthrough ties the phases together and motivates the sequencing.
- [ ] At least one diagram or supplemental table clarifies flow or decision points.
- [ ] Risk analysis includes both tabular assessment and mitigation tasks.
- [ ] Outcome snapshot describes the observable state once the plan lands.
- [ ] References to related docs and artifacts are embedded where helpful.

## Review Guidance

Reviewers should verify that success criteria are measurable, risks have credible mitigations, and references point to concrete artefacts. Request revisions whenever rationale is missing or when additional visuals would clarify the design.
