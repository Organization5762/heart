#!/usr/bin/env python3
"""Generate Python protobuf modules for Heart schemas."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_PROTO_PATH = Path("src")
DEFAULT_PYTHON_OUT = Path("src")

app = typer.Typer(add_completion=False)


@app.command()
def generate(
    proto: list[Path] = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    proto_path: Path = typer.Option(
        DEFAULT_PROTO_PATH,
        "--proto-path",
        help="Root directory for protobuf imports.",
    ),
    python_out: Path = typer.Option(
        DEFAULT_PYTHON_OUT,
        "--python-out",
        help="Output directory for generated Python modules.",
    ),
) -> None:
    """Compile .proto files into *_pb2.py modules."""
    proto_path = proto_path.resolve()
    python_out = python_out.resolve()
    python_out.mkdir(parents=True, exist_ok=True)

    args = [
        "protoc",
        f"--proto_path={proto_path}",
        f"--python_out={python_out}",
        *(str(path) for path in proto),
    ]
    logger.info("Generating protobuf modules: %s", ", ".join(path.name for path in proto))
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("Protobuf generation failed with exit code %s.", exc.returncode)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
