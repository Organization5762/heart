# Renderer Responsibilities

## Problem

Renderer stacks were mixing concerns by assembling scene lists in provider classes. This makes
it harder to see where state is defined, where events update state, and where pixels are drawn.

## Roles

- **State** defines the data object that is iterated on. For example, scene lists are stored in
  state objects such as `heart.renderers.artist.state.ArtistState` and
  `heart.renderers.kirby.state.KirbyState`.
- **Provider** updates state in response to event streams. Providers should not perform renderer
  initialization or scene construction.
- **Renderer** converts the current state snapshot into pixels (or coordinates child renderers
  that do).

## Materials

- `src/heart/renderers/artist/state.py`
- `src/heart/renderers/kirby/state.py`
- `src/heart/renderers/slide_transition/renderer.py`
