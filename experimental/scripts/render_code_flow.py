#!/usr/bin/env python3
"""Render the runtime code flow mermaid diagram to an image file."""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable


def extract_mermaid_blocks(markdown: str) -> Iterable[str]:
    """Yield mermaid code blocks from a markdown document."""
    lines = markdown.splitlines()
    in_block = False
    block_lines: list[str] = []

    for line in lines:
        if not in_block:
            if line.strip().lower().startswith("```mermaid"):
                in_block = True
                block_lines = []
            continue

        if line.strip().startswith("```"):
            in_block = False
            if block_lines:
                yield "\n".join(block_lines).strip() + "\n"
            block_lines = []
        else:
            block_lines.append(line)


def ensure_renderer() -> list[str]:
    """Return the command to invoke the mermaid CLI."""
    mmdc = shutil.which("mmdc")
    if mmdc:
        return [mmdc]

    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "@mermaid-js/mermaid-cli"]

    raise SystemExit(
        "Neither 'mmdc' nor 'npx' with @mermaid-js/mermaid-cli is available. "
        "Install the mermaid CLI (https://github.com/mermaid-js/mermaid-cli) "
        "or ensure Node.js with npx is on PATH."
    )


def render_diagram(source: str, output: pathlib.Path, fmt: str) -> None:
    render_cmd = ensure_renderer()

    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as tmp:
        tmp.write(source)
        tmp_path = pathlib.Path(tmp.name)

    try:
        cmd = [*render_cmd, "-i", str(tmp_path), "-o", str(output), "-t", "neutral", "-e", fmt]
        subprocess.run(cmd, check=True)
    finally:
        tmp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=pathlib.Path,
        default=pathlib.Path("docs/code_flow.md"),
        help="Markdown file that contains a mermaid diagram.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("docs/code_flow.svg"),
        help="Output image path (format inferred from extension).",
    )
    parser.add_argument(
        "--format",
        choices=["svg", "png", "pdf"],
        help="Explicit format override (otherwise derived from output extension).",
    )
    args = parser.parse_args(argv)

    if not args.source.exists():
        raise SystemExit(f"Markdown source not found: {args.source}")

    markdown = args.source.read_text(encoding="utf-8")
    blocks = list(extract_mermaid_blocks(markdown))
    if not blocks:
        raise SystemExit(f"No mermaid diagram found in {args.source}")

    mermaid_source = blocks[0]

    output_format = args.format
    if output_format is None:
        output_format = args.output.suffix.lstrip(".").lower() or "svg"

    if output_format not in {"svg", "png", "pdf"}:
        raise SystemExit(f"Unsupported output format: {output_format}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    render_diagram(mermaid_source, args.output, output_format)
    return 0


if __name__ == "__main__":
    sys.exit(main())
