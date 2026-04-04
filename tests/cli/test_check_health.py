"""Validate the totem host health check so Raspberry Pi deployments can surface throttling regressions quickly."""

from __future__ import annotations

import subprocess

import pytest
import typer

from heart.cli.commands.check_health import (THROTTLED_COMMAND,
                                             check_health_command,
                                             parse_throttled_output,
                                             summarize_throttled_mask)


class TestThrottledParsing:
    """Exercise throttle parsing helpers so the health check stays reliable across Raspberry Pi command output variants."""

    @pytest.mark.parametrize(
        ("output", "expected_mask"),
        [
            pytest.param("throttled=0x0\n", 0x0, id="healthy"),
            pytest.param("throttled=0x50005\n", 0x50005, id="current-and-history"),
            pytest.param("status ok\nthrottled=0x20000\n", 0x20000, id="extra-prefix"),
        ],
    )
    def test_parse_throttled_output_extracts_hex_mask(
        self, output: str, expected_mask: int
    ) -> None:
        """Verify throttled output parsing accepts the Raspberry Pi hex payload so operator checks decode health bits accurately."""

        assert parse_throttled_output(output) == expected_mask

    def test_parse_throttled_output_rejects_unknown_format(self) -> None:
        """Verify malformed throttled output is rejected so the health command does not silently report a false clean bill of health."""

        with pytest.raises(ValueError):
            parse_throttled_output("gpu=ready\n")


class TestThrottledSummaries:
    """Validate bitmask summaries so the health command distinguishes current throttling from historical events."""

    def test_summarize_throttled_mask_separates_current_and_historical_flags(
        self,
    ) -> None:
        """Verify decoded masks split active and past issues so operators can tell whether a problem is happening now or only occurred earlier."""

        summary = summarize_throttled_mask(0x50005)

        assert summary.current_issues == (
            "under-voltage detected",
            "currently throttled",
        )
        assert summary.historical_issues == (
            "under-voltage has occurred",
            "throttling has occurred",
        )
        assert summary.has_current_issues is True


class TestCheckHealthCommand:
    """Cover the CLI command path so totem hosts get stable output and exit codes from the new health utility."""

    def test_check_health_command_reports_healthy_pi(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify a zero throttled mask prints a passing status so operators can confirm the Pi is not currently constrained."""

        def _run(
            command: tuple[str, ...], *, capture_output: bool, check: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            assert command == THROTTLED_COMMAND
            assert capture_output is True
            assert check is False
            assert text is True
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="throttled=0x0\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", _run)

        check_health_command()

        assert capsys.readouterr().out.splitlines() == [
            "vcgencmd get_throttled: 0x0",
            "Current issues: none",
            "Historical issues: none",
            "Health check passed: no current Raspberry Pi throttling flags are active.",
        ]

    def test_check_health_command_allows_historical_issues_when_current_state_is_clear(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify historical throttling stays non-fatal so the command answers the operational question of whether the Pi is constrained right now."""

        def _run(
            command: tuple[str, ...], *, capture_output: bool, check: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="throttled=0x50000\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", _run)

        check_health_command()

        assert capsys.readouterr().out.splitlines() == [
            "vcgencmd get_throttled: 0x50000",
            "Current issues: none",
            "Historical issues: under-voltage has occurred, throttling has occurred",
            "Health check passed: no current Raspberry Pi throttling flags are active.",
        ]

    def test_check_health_command_fails_when_current_issues_are_active(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify active throttling exits non-zero so automation can stop and investigate a Pi that is currently power or thermal constrained."""

        def _run(
            command: tuple[str, ...], *, capture_output: bool, check: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="throttled=0x50005\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", _run)

        with pytest.raises(typer.Exit) as error:
            check_health_command()

        assert error.value.exit_code == 1
        assert capsys.readouterr().out.splitlines() == [
            "vcgencmd get_throttled: 0x50005",
            "Current issues: under-voltage detected, currently throttled",
            "Historical issues: under-voltage has occurred, throttling has occurred",
            "Health check failed: Raspberry Pi power or thermal throttling is currently active.",
        ]

    def test_check_health_command_fails_when_vcgencmd_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify command execution failures exit non-zero so deployment checks do not hide a missing or broken Raspberry Pi tooling setup."""

        def _run(
            command: tuple[str, ...], *, capture_output: bool, check: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="vcgencmd: command not registered",
            )

        monkeypatch.setattr(subprocess, "run", _run)

        with pytest.raises(typer.Exit) as error:
            check_health_command()

        assert error.value.exit_code == 1
