#!/usr/bin/env python3
"""Calm, parameterized entrypoint for retained HUB75 laboratory work."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def _prepare_repo_python() -> None:
    """Use the repository environment when invoked directly."""

    sys.path.insert(0, str(REPO_ROOT / "src"))
    if (
        __name__ == "__main__"
        and VENV_PYTHON.is_file()
        and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    ):
        os.execv(
            VENV_PYTHON,
            (str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]),
        )


_prepare_repo_python()

from heart.utilities.hub75_lab.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
