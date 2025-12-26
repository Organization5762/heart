# Rendering Experiments

## Problem Statement

Track experimental rendering notes in a single place so renderer experiments stay discoverable
without scattering short files across the docs tree.

## Channel Diffusion

Channel diffusion explores diffusion-like redistribution of RGB energy across a grid. The
current implementation lives in:

- `src/heart/renderers/channel_diffusion/renderer.py`
- `src/heart/renderers/channel_diffusion/provider.py`
- `src/heart/renderers/channel_diffusion/state.py`

Configuration entry point:

- `src/heart/programs/configurations/channel_diffusion.py`

## Color Conversion Tuning

Color conversion tuning captures heuristics for converting between RGB and other color spaces
used in LED rendering. Reference implementations live in
`src/heart/renderers/color_conversion`.
