# Display resolution detection

The local device driver relies on platform-specific helpers to determine the host
screen dimensions before scaling rendered frames.

* `src/heart/device/local.py` defines three providers that implement
  `DisplayResolutionProvider`:
  * `MacDisplayResolutionProvider` parses `system_profiler SPDisplaysDataType`
    output and extracts the primary display resolution.
  * `XrandrDisplayResolutionProvider` inspects `xrandr --query` output to
    support Linux and X11 forwarding scenarios.
  * `FallbackDisplayResolutionProvider` emits the default 1920×1080 resolution
    for platforms that do not expose a detection path.
* `_get_display_resolution()` remains the module-level entry point, caching the
  detected result via `functools.lru_cache` so other call sites can continue to
  use the helper without change.

All providers log their detection status and revert to the shared default of
1920×1080 (16:9) when parsing fails or system utilities are unavailable.
