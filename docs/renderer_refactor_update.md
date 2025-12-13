# Renderer refactor updates

## Summary

- Split the combined BPM playlist into `combined_bpm_screen/{provider.py,state.py,renderer.py}` so timer handling now lives in `CombinedBpmScreenStateProvider` while the renderer only delegates to metadata and max-BPM screens.
- Migrated metadata HUD logic into `metadata_screen/{provider.py,state.py,renderer.py}` with `MetadataScreenStateProvider` streaming animation state for each monitor.

## Notes for implementers

- Providers subscribe to `PeripheralManager.game_tick` alongside the shared clock stream to keep frame timing consistent with other water- and life-style renderers.
- Both renderers dispose provider subscriptions in `reset` to prevent dangling observers when playlists switch scenes.
