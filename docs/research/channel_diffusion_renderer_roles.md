# Channel diffusion renderer role split

## Summary

Channel diffusion rendering now separates state updates from pixel output. The
state update logic lives in a provider, while the renderer focuses on converting
the current state grid into pixels for the display surface.

## Notes

- State initialization and diffusion updates moved into
  `heart.renderers.channel_diffusion.provider.ChannelDiffusionStateProvider`.
- `heart.renderers.channel_diffusion.renderer.ChannelDiffusionRenderer` now
  delegates state updates to the provider before blitting pixels.

## Materials

- `src/heart/renderers/channel_diffusion/provider.py`
- `src/heart/renderers/channel_diffusion/renderer.py`
- `src/heart/renderers/channel_diffusion/state.py`
