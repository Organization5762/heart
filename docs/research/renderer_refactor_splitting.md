# Renderer module split notes

## Summary

This refactor standardizes several legacy renderers so they match the provider/state/renderer split already used by components like the water title screen. The following modules were restructured into packages with dedicated provider, state, and renderer files:

- `spritesheet_random` now exposes `state.py`, `provider.py`, and `renderer.py` for the looped spritesheet animation.
- `yolisten` separates the PhyPhox-driven word animation into the same three-file layout.
- `pixels` breaks out the Border, Rain, and Slinky effects to share explicit providers and state containers.

## Rationale

Each renderer previously mixed peripheral subscriptions, state storage, and drawing logic in a single module. Splitting responsibilities clarifies which code owns device inputs and which code mutates render state, mirroring the pattern established in `water_title_screen`. The providers now handle switch subscriptions and initial state creation, while renderer files focus on frame updates.

## Impacted code paths

- `src/heart/display/renderers/spritesheet_random/`
- `src/heart/display/renderers/yolisten/`
- `src/heart/display/renderers/pixels/`

These packages continue exporting the same renderer classes, so existing program configurations importing `SpritesheetLoopRandom`, `YoListenRenderer`, `Border`, `Rain`, or `Slinky` keep working.
