"""Operator health checks for Raspberry Pi totem hosts."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

import typer

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

THROTTLED_COMMAND = ("vcgencmd", "get_throttled")
NO_FLAGS_LABEL = "none"
THROTTLED_OUTPUT_PATTERN = re.compile(r"throttled=(0x[0-9a-fA-F]+)")
CURRENT_THROTTLED_FLAGS = (
    (0, "under-voltage detected"),
    (1, "arm frequency capped"),
    (2, "currently throttled"),
    (3, "soft temperature limit active"),
)
HISTORICAL_THROTTLED_FLAGS = (
    (16, "under-voltage has occurred"),
    (17, "arm frequency capping has occurred"),
    (18, "throttling has occurred"),
    (19, "soft temperature limit has occurred"),
)


@dataclass(frozen=True, slots=True)
class ThrottledStatus:
    """Decoded Raspberry Pi throttle state from ``vcgencmd get_throttled``."""

    mask: int
    current_issues: tuple[str, ...]
    historical_issues: tuple[str, ...]

    @property
    def has_current_issues(self) -> bool:
        """Return whether the Pi currently reports power or thermal constraints."""

        return bool(self.current_issues)


def parse_throttled_output(output: str) -> int:
    """Extract the hexadecimal throttle mask from ``vcgencmd`` output."""

    match = THROTTLED_OUTPUT_PATTERN.search(output)
    if match is None:
        raise ValueError(f"Unexpected throttled output: {output.strip()!r}")
    return int(match.group(1), 16)


def summarize_throttled_mask(mask: int) -> ThrottledStatus:
    """Split throttle bits into current and historical issue labels."""

    current_issues = tuple(
        description
        for bit, description in CURRENT_THROTTLED_FLAGS
        if mask & (1 << bit)
    )
    historical_issues = tuple(
        description
        for bit, description in HISTORICAL_THROTTLED_FLAGS
        if mask & (1 << bit)
    )
    return ThrottledStatus(
        mask=mask,
        current_issues=current_issues,
        historical_issues=historical_issues,
    )


def _render_issues(issues: tuple[str, ...]) -> str:
    """Return a stable operator-facing description for issue lists."""

    return ", ".join(issues) if issues else NO_FLAGS_LABEL


def check_health_command() -> None:
    """Run host health checks that matter for Raspberry Pi totem deployments."""

    try:
        result = subprocess.run(
            THROTTLED_COMMAND,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        logger.exception("Failed to run %s", " ".join(THROTTLED_COMMAND))
        raise typer.Exit(code=1) from error

    if result.returncode != 0:
        logger.error(
            "%s failed with exit code %s: %s",
            " ".join(THROTTLED_COMMAND),
            result.returncode,
            result.stderr.strip() or result.stdout.strip(),
        )
        raise typer.Exit(code=1)

    try:
        throttled_status = summarize_throttled_mask(parse_throttled_output(result.stdout))
    except ValueError as error:
        logger.error("Failed to parse throttled output: %s", result.stdout.strip())
        raise typer.Exit(code=1) from error

    typer.echo(f"vcgencmd get_throttled: 0x{throttled_status.mask:x}")
    typer.echo(f"Current issues: {_render_issues(throttled_status.current_issues)}")
    typer.echo(
        f"Historical issues: {_render_issues(throttled_status.historical_issues)}"
    )

    if throttled_status.has_current_issues:
        typer.echo(
            "Health check failed: Raspberry Pi power or thermal throttling is currently active."
        )
        raise typer.Exit(code=1)

    typer.echo(
        "Health check passed: no current Raspberry Pi throttling flags are active."
    )
