# Visual hierarchy in Beats

## Purpose

This README documents how the Beats experimental UI expresses visual hierarchy so
contributors can make consistent layout and styling decisions.

## Visual hierarchy goals

- Make primary actions and current focus obvious.
- Separate navigation, content, and supporting detail without relying on
  additional copy.
- Keep the reading order predictable across screens.

## Hierarchy signals

### Layout structure

- Use a primary content column with a consistent max width.
- Reserve a dedicated area for navigation and status indicators.
- Group related controls in visually distinct containers.

### Typography

- Use one font family with multiple weights to express emphasis.
- Titles are larger and heavier than section headers.
- Supporting text stays at a smaller size with reduced contrast.

### Color and contrast

- Primary actions use the strongest contrast available in the palette.
- Secondary actions use muted contrast and reduced fill weight.
- Backgrounds for grouped content have lower contrast than the page surface.

### Spacing and density

- Increase spacing around primary content blocks.
- Use tighter spacing for supporting metadata.
- Keep consistent vertical rhythm between sections.

### Motion (when applicable)

- Use short, subtle transitions to reinforce focus changes.
- Avoid motion for decorative purposes.

## Materials

- Color palette tokens (see `src/styles` in this package).
- Typography tokens (font sizes and weights in `src/styles`).
- Component-level layout primitives (see `src/components`).

## Updating this document

If the hierarchy rules change, update this README alongside the relevant style
or component updates.
