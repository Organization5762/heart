#!/usr/bin/env python3
"""Run a restartable developer session for the Heart runtime."""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from heart.utilities.logging import get_logger


WATCH_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".json"}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
logger = get_logger(__name__)


@dataclass(frozen=True)
class SessionConfig:
    """Configuration for a developer session."""

    configuration: str
    add_low_power_mode: bool
    x11_forward: bool
    render_variant: str | None
    watch: bool
    poll_interval: float
    debounce_seconds: float
    watch_paths: tuple[Path, ...]
    extra_args: tuple[str, ...]


@dataclass
class SessionState:
    """Runtime state for the developer session."""

    snapshot: dict[Path, float]
    last_restart: float


def resolve_repo_root() -> Path:
    """Resolve the git repository root or fall back to the cwd."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return Path.cwd()


def _should_watch_path(path: Path, repo_root: Path) -> bool:
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        return False
    if any(part in SKIP_DIRS for part in relative.parts):
        return False
    return path.suffix in WATCH_SUFFIXES


def snapshot_paths(paths: Iterable[Path], repo_root: Path) -> dict[Path, float]:
    """Capture a snapshot of file modification times."""

    snapshot: dict[Path, float] = {}
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if not _should_watch_path(path, repo_root):
                continue
            snapshot[path] = path.stat().st_mtime
    return snapshot


def has_changes(state: SessionState, config: SessionConfig, repo_root: Path) -> bool:
    """Return True when watched files have changed."""

    now = time.monotonic()
    if now - state.last_restart < config.debounce_seconds:
        return False
    current_snapshot = snapshot_paths(config.watch_paths, repo_root)
    if current_snapshot != state.snapshot:
        state.snapshot = current_snapshot
        state.last_restart = now
        return True
    return False


def build_command(config: SessionConfig) -> list[str]:
    """Build the totem run command."""

    command = ["uv", "run", "totem", "run", "--configuration", config.configuration]
    if config.x11_forward:
        command.append("--x11-forward")
    if not config.add_low_power_mode:
        command.append("--no-add-low-power-mode")
    command.extend(config.extra_args)
    return command


def prepare_env(config: SessionConfig) -> dict[str, str]:
    """Prepare environment variables for the session."""

    env = os.environ.copy()
    if config.render_variant:
        env["HEART_RENDER_VARIANT"] = config.render_variant
    return env


def run_session(config: SessionConfig, repo_root: Path) -> int:
    """Run the restartable development session."""

    command = build_command(config)
    env = prepare_env(config)
    logger.info("Developer session starting...")
    logger.info("Command: %s", " ".join(command))
    if config.watch:
        logger.info("Watch paths:")
        for path in config.watch_paths:
            logger.info("  - %s", path)

    state = SessionState(
        snapshot=snapshot_paths(config.watch_paths, repo_root),
        last_restart=0.0,
    )

    while True:
        process = subprocess.Popen(command, cwd=repo_root, env=env)
        if not config.watch:
            return process.wait()

        while process.poll() is None:
            time.sleep(config.poll_interval)
            if has_changes(state, config, repo_root):
                logger.info("Change detected. Restarting the runtime...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
        else:
            return process.returncode or 0


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run a restartable Heart runtime session for development.",
    )
    parser.add_argument(
        "--configuration",
        default="lib_2025",
        help="Configuration name from heart.programs.configurations.",
    )
    parser.add_argument(
        "--no-add-low-power-mode",
        dest="add_low_power_mode",
        action="store_false",
        help="Disable the low power mode added after scene setup.",
    )
    parser.add_argument(
        "--x11-forward",
        action="store_true",
        help="Force the X11 pygame window for RGB display testing.",
    )
    parser.add_argument(
        "--render-variant",
        help="Override HEART_RENDER_VARIANT for this session.",
    )
    parser.add_argument(
        "--no-watch",
        dest="watch",
        action="store_false",
        help="Run the runtime once without watching for changes.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds for file change checks.",
    )
    parser.add_argument(
        "--debounce-seconds",
        type=float,
        default=0.35,
        help="Minimum time between restarts in seconds.",
    )
    parser.add_argument(
        "--watch-path",
        action="append",
        default=[],
        help="Additional paths to watch for changes.",
    )
    parser.add_argument(
        "--no-default-watch",
        action="store_true",
        help="Disable the default watch paths for the runtime session.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="devex-session 1.0",
    )
    return parser.parse_known_args()


def resolve_watch_paths(
    repo_root: Path,
    provided_paths: Iterable[str],
    include_defaults: bool,
) -> tuple[Path, ...]:
    paths: list[Path] = []
    if include_defaults:
        paths.extend(
            [
                repo_root / "src",
                repo_root / "drivers",
                repo_root / "experimental",
                repo_root / "scripts",
            ]
        )
    for path in provided_paths:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        paths.append(candidate)
    return tuple(dict.fromkeys(paths))


def main() -> int:
    args, extra_args = parse_args()
    repo_root = resolve_repo_root()
    watch_paths = resolve_watch_paths(
        repo_root,
        args.watch_path,
        include_defaults=not args.no_default_watch,
    )
    config = SessionConfig(
        configuration=args.configuration,
        add_low_power_mode=args.add_low_power_mode,
        x11_forward=args.x11_forward,
        render_variant=args.render_variant,
        watch=args.watch,
        poll_interval=args.poll_interval,
        debounce_seconds=args.debounce_seconds,
        watch_paths=watch_paths,
        extra_args=tuple(extra_args),
    )
    return run_session(config, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
