#!/usr/bin/env python3
"""Capture a repeatable developer experience snapshot for Heart."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    output: str


def _run_command(command: Iterable[str]) -> CommandResult:
    command_list = list(command)
    result = subprocess.run(
        command_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return CommandResult(
        command=" ".join(command_list),
        exit_code=result.returncode,
        output=result.stdout.strip(),
    )


def _command_output(command: Iterable[str]) -> str | None:
    result = _run_command(command)
    if result.exit_code != 0:
        return None
    return result.output


def _git_snapshot() -> dict[str, object] | None:
    if not shutil.which("git"):
        return None

    inside = _command_output(["git", "rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return None

    root = _command_output(["git", "rev-parse", "--show-toplevel"]) or "unknown"
    branch = _command_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    commit = _command_output(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
    status_lines = _command_output(["git", "status", "--porcelain"]) or ""
    dirty = bool(status_lines.strip())
    return {
        "root": root,
        "branch": branch,
        "commit": commit,
        "dirty": dirty,
        "changed_files": len([line for line in status_lines.splitlines() if line.strip()]),
    }


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {
        "uv": None,
        "python": platform.python_version(),
        "git": None,
    }
    if shutil.which("uv"):
        versions["uv"] = _command_output(["uv", "--version"])
    if shutil.which("git"):
        versions["git"] = _command_output(["git", "--version"])
    return versions


def _env_snapshot() -> dict[str, str | None]:
    return {
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "uv_project_env": os.environ.get("UV_PROJECT_ENVIRONMENT"),
        "python_executable": sys.executable,
    }


def _snapshot_payload() -> dict[str, object]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "tools": _tool_versions(),
        "environment": _env_snapshot(),
        "repository": _git_snapshot(),
    }


def _format_text(payload: dict[str, object]) -> str:
    lines: list[str] = ["Devex Snapshot"]
    lines.append(f"Timestamp (UTC): {payload['timestamp_utc']}")
    platform_data = payload["platform"]
    lines.append(
        "Platform: {system} {release} ({machine})".format(
            **platform_data
        )
    )
    python_data = payload["python"]
    lines.append(
        "Python: {version} ({implementation})".format(**python_data)
    )
    tools = payload["tools"]
    lines.append(f"uv: {tools.get('uv') or 'missing'}")
    lines.append(f"git: {tools.get('git') or 'missing'}")
    env = payload["environment"]
    lines.append(f"Virtual env: {env.get('virtual_env') or 'not set'}")
    lines.append(f"uv project env: {env.get('uv_project_env') or 'not set'}")
    lines.append(f"Python executable: {env.get('python_executable')}")
    repo = payload.get("repository")
    if repo:
        lines.append("Repository:")
        lines.append(f"  Root: {repo.get('root')}")
        lines.append(f"  Branch: {repo.get('branch')}")
        lines.append(f"  Commit: {repo.get('commit')}")
        lines.append(f"  Dirty: {repo.get('dirty')}")
        lines.append(f"  Changed files: {repo.get('changed_files')}")
    else:
        lines.append("Repository: not detected")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a developer experience snapshot for troubleshooting."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the snapshot.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to write the snapshot output.",
    )
    args = parser.parse_args()

    payload = _snapshot_payload()
    if args.format == "json":
        output = json.dumps(payload, indent=2, sort_keys=True)
    else:
        output = _format_text(payload)

    if args.output:
        output_path: Path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{output}\n", encoding="utf-8")
    else:
        sys.stdout.write(f"{output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
