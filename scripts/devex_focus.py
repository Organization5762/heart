#!/usr/bin/env python3
"""Run a change-aware developer feedback loop."""

from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FocusTargets:
    """Group the files relevant to developer feedback loops."""

    python_files: tuple[Path, ...]
    doc_files: tuple[Path, ...]
    test_files: tuple[Path, ...]

    @property
    def has_targets(self) -> bool:
        return bool(self.python_files or self.doc_files or self.test_files)


def resolve_repo_root() -> Path:
    """Return the git repository root or the current working directory."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return Path.cwd()


def collect_paths_from_git(repo_root: Path, base: str) -> set[Path]:
    """Return changed and untracked paths when available."""

    paths: set[Path] = set()
    git_commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", base],
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    for command in git_commands:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            candidate = (repo_root / line.strip()).resolve()
            if candidate.exists():
                paths.add(candidate)
    return paths


def collect_paths_from_directories(repo_root: Path) -> set[Path]:
    """Fallback to scanning common project directories."""

    paths: set[Path] = set()
    for folder in ("src", "tests", "docs", "scripts"):
        root = repo_root / folder
        if not root.exists():
            continue
        for candidate in root.rglob("*"):
            if candidate.is_file():
                paths.add(candidate.resolve())
    return paths


def collect_focus_targets(repo_root: Path, base: str) -> FocusTargets:
    """Collect the files that should be formatted, linted, or tested."""

    paths = collect_paths_from_git(repo_root, base)
    if not paths:
        paths = collect_paths_from_directories(repo_root)

    python_files: list[Path] = []
    doc_files: list[Path] = []
    test_files: list[Path] = []

    for path in paths:
        if path.suffix != ".py" and path.suffix != ".md":
            continue
        try:
            relative = path.relative_to(repo_root)
        except ValueError:
            continue
        if ".venv" in relative.parts:
            continue
        if path.suffix == ".py":
            python_files.append(path)
            if relative.parts and relative.parts[0] == "tests":
                test_files.append(path)
        if path.suffix == ".md" and relative.parts and relative.parts[0] == "docs":
            doc_files.append(path)

    return FocusTargets(
        python_files=tuple(sorted(python_files)),
        doc_files=tuple(sorted(doc_files)),
        test_files=tuple(sorted(test_files)),
    )


def run_command(command: list[str], repo_root: Path) -> int:
    """Run a subprocess command and return the exit code."""

    display = " ".join(command)
    print(f"\n> {display}")
    result = subprocess.run(command, check=False, cwd=repo_root)
    return result.returncode


def run_formatting(targets: FocusTargets, repo_root: Path, mode: str) -> list[int]:
    """Run format or check commands for the collected targets."""

    exit_codes: list[int] = []
    if targets.python_files:
        python_args = [str(path.relative_to(repo_root)) for path in targets.python_files]
        if mode == "format":
            exit_codes.append(run_command(["uvx", "isort", *python_args], repo_root))
            exit_codes.append(
                run_command(["uvx", "ruff", "check", "--fix", *python_args], repo_root)
            )
        else:
            exit_codes.append(
                run_command(["uvx", "isort", "--check-only", *python_args], repo_root)
            )
            exit_codes.append(
                run_command(["uvx", "ruff", "check", *python_args], repo_root)
            )
    if targets.doc_files:
        doc_args = [str(path.relative_to(repo_root)) for path in targets.doc_files]
        if mode == "format":
            exit_codes.append(
                run_command(
                    [
                        "uvx",
                        "docformatter",
                        "-i",
                        "--config",
                        "./pyproject.toml",
                        *doc_args,
                    ],
                    repo_root,
                )
            )
            exit_codes.append(run_command(["uvx", "mdformat", *doc_args], repo_root))
        else:
            exit_codes.append(
                run_command(
                    [
                        "uvx",
                        "docformatter",
                        "--check",
                        "--config",
                        "./pyproject.toml",
                        *doc_args,
                    ],
                    repo_root,
                )
            )
            exit_codes.append(
                run_command(["uvx", "mdformat", "--check", *doc_args], repo_root)
            )
    return exit_codes


def run_tests(
    targets: FocusTargets,
    repo_root: Path,
    test_scope: str,
) -> list[int]:
    """Run test commands based on the requested scope."""

    exit_codes: list[int] = []
    if test_scope == "none":
        print("\n> Skipping tests (--test-scope none)")
        return exit_codes

    if test_scope == "changed":
        if not targets.test_files:
            print("\n> No changed tests detected")
            return exit_codes
        test_args = [str(path.relative_to(repo_root)) for path in targets.test_files]
        exit_codes.append(run_command(["uv", "run", "pytest", *test_args], repo_root))
        return exit_codes

    if test_scope == "changed-or-last-failed":
        if targets.test_files:
            test_args = [str(path.relative_to(repo_root)) for path in targets.test_files]
            exit_codes.append(run_command(["uv", "run", "pytest", *test_args], repo_root))
            return exit_codes
        last_failed = repo_root / ".pytest_cache" / "v" / "cache" / "lastfailed"
        if last_failed.exists():
            exit_codes.append(run_command(["uv", "run", "pytest", "--lf"], repo_root))
        else:
            print("\n> No changed tests or last-failed cache found")
        return exit_codes

    if test_scope == "all":
        exit_codes.append(run_command(["uv", "run", "pytest"], repo_root))
        return exit_codes

    raise ValueError(f"Unknown test scope: {test_scope}")


def run_focus(
    repo_root: Path,
    base: str,
    mode: str,
    test_scope: str,
) -> int:
    """Run the focus loop once and return an exit status."""

    targets = collect_focus_targets(repo_root, base)
    if not targets.has_targets:
        print("No matching files found for focus checks.")
        return 0

    print("Focus targets:")
    print(f"  Python files: {len(targets.python_files)}")
    print(f"  Docs files: {len(targets.doc_files)}")
    print(f"  Test files: {len(targets.test_files)}")

    exit_codes: list[int] = []
    exit_codes.extend(run_formatting(targets, repo_root, mode))
    exit_codes.extend(run_tests(targets, repo_root, test_scope))

    return 0 if all(code == 0 for code in exit_codes) else 1


def snapshot_paths(watch_paths: Iterable[Path]) -> dict[Path, float]:
    """Capture file modification times for the watch loop."""

    snapshot: dict[Path, float] = {}
    for root in watch_paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".md"}:
                continue
            snapshot[path] = path.stat().st_mtime
    return snapshot


def watch_focus(
    repo_root: Path,
    base: str,
    mode: str,
    test_scope: str,
    watch_paths: Iterable[Path],
    poll_interval: float,
) -> int:
    """Watch for changes and rerun the focus loop."""

    status = run_focus(repo_root, base, mode, test_scope)
    previous_snapshot = snapshot_paths(watch_paths)
    while True:
        time.sleep(poll_interval)
        current_snapshot = snapshot_paths(watch_paths)
        if current_snapshot != previous_snapshot:
            status = run_focus(repo_root, base, mode, test_scope)
            previous_snapshot = current_snapshot
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run change-aware formatting and tests for fast developer feedback.",
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Git base reference used to detect changes (default: HEAD).",
    )
    parser.add_argument(
        "--mode",
        choices=("check", "format"),
        default="format",
        help="Whether to format changes or just check them.",
    )
    parser.add_argument(
        "--test-scope",
        choices=("changed", "changed-or-last-failed", "all", "none"),
        default="changed-or-last-failed",
        help="Control how tests are selected for the focus loop.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for file changes and rerun the focus loop.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds when watch mode is enabled.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = resolve_repo_root()
    watch_paths = [repo_root / "src", repo_root / "tests", repo_root / "docs"]
    watch_paths.append(repo_root / "scripts")

    if args.watch:
        return watch_focus(
            repo_root,
            args.base,
            args.mode,
            args.test_scope,
            watch_paths,
            args.poll_interval,
        )
    return run_focus(repo_root, args.base, args.mode, args.test_scope)


if __name__ == "__main__":
    raise SystemExit(main())
