"""Internal execution adapter for already-validated HUB75 experiment plans."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import final


def run_experiment_command(command: ExperimentCommand) -> None:
    """Execute one fully resolved experiment command."""

    environment = os.environ.copy()
    environment.update(command.environment)
    subprocess.run(
        command.argv,
        cwd=command.cwd,
        env=environment,
        check=True,
    )


@final
@dataclass(frozen=True)
class ExperimentCommand:
    """A printable, executable command with explicit environment."""

    argv: tuple[str, ...]
    environment: dict[str, str]
    cwd: Path
    safety_evidence: tuple[str, ...]
    applied_settings: dict[str, object]
    fixed_invariants: dict[str, object]
