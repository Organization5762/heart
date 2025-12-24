# Developer Session Runner

## Problem Statement

Local iteration on the Heart runtime can be slow when every code change requires manually
stopping and restarting the `totem` process. Developers need a lightweight loop that keeps the
runtime running, restarts it on relevant file changes, and makes configuration overrides easy to
apply.

## Materials

- Python 3.11+ with the Heart runtime installed.
- `uv` for running repository tooling.
- A local display stack (SDL-compatible) when running the pygame window.

## Concept

The developer session runner watches the runtime sources and restarts `totem run` whenever a
watched file changes. It keeps the edit ➜ run loop tight without asking developers to manually
manage process restarts. The runner also supports per-session overrides such as configuration
selection, render variant, or X11 forwarding.

## Usage

Start a restartable session with the default configuration:

```bash
make dev-session
```

Override the configuration and render variant:

```bash
uv run python scripts/devex_session.py --configuration lib_2024 --render-variant parallel
```

Disable file watching and run once:

```bash
uv run python scripts/devex_session.py --no-watch
```

Add extra watch paths or disable the defaults:

```bash
uv run python scripts/devex_session.py --no-default-watch --watch-path src/heart/programs
```

## Defaults

By default, the session watches these paths relative to the repository root:

- `src/`
- `drivers/`
- `experimental/`
- `scripts/`

It restarts after a short debounce window (0.35 seconds) and polls for changes every 0.5 seconds.

## Configuration Notes

- Use `--render-variant` to temporarily set `HEART_RENDER_VARIANT` for the session.
- Pass additional `totem run` flags after the arguments accepted by the session runner. Unknown
  flags are forwarded to `totem run` as-is.
