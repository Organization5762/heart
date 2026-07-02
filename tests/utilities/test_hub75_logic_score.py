from __future__ import annotations

import csv
from pathlib import Path

import pytest

from heart.utilities.hub75_logic_score import (diagnose_hub75_capture,
                                               load_hub75_logic_csv,
                                               score_hub75_similarity,
                                               summarize_hub75_capture)

DEFAULT_HEADERS = ("Time [s]", "CLK", "LAT", "OE", "A", "B", "C", "D", "E")


class TestHub75LogicScore:
    """Group HUB75 logic-score tests so electrical regressions stay measurable."""

    def test_identical_capture_scores_as_perfect_match(self, tmp_path: Path) -> None:
        """Verify identical captures score 1.0 so the baseline anchor remains stable."""

        capture_path = tmp_path / "baseline.csv"
        _write_capture_csv(capture_path, _build_capture_rows())

        capture = load_hub75_logic_csv(capture_path)
        summary = summarize_hub75_capture(capture, cols=4)
        score = score_hub75_similarity(summary, summary)

        assert summary.valid_hub75 is True
        assert summary.row_clock_mismatch_count == 0
        assert summary.lat_while_output_enabled_count == 0
        assert 0.0 < summary.oe_active_fraction < 1.0
        assert summary.oe_active_fraction + summary.oe_blank_fraction == pytest.approx(
            1.0
        )
        assert summary.median_oe_active_ns is not None
        assert summary.median_oe_blank_ns is not None
        assert summary.p99_oe_blank_ns is not None
        assert summary.max_oe_blank_ns is not None
        assert summary.long_oe_blank_count == 0
        assert summary.p99_clk_period_ns is not None
        assert summary.max_clk_period_ns is not None
        assert summary.long_clk_period_count == 0
        assert summary.address_edge_counts["A"] > 0
        assert summary.max_address_edge_interval_ns["A"] is not None
        assert score.total == pytest.approx(1.0)

    def test_extra_clock_pulse_reduces_similarity(self, tmp_path: Path) -> None:
        """Verify an extra in-row clock reduces the score so row-shift drift is visible."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture_csv(baseline_path, _build_capture_rows())
        _write_capture_csv(candidate_path, _build_capture_rows(extra_clock_row=1))

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert candidate.row_clock_mismatch_count == 1
        assert score.total < 1.0
        assert score.control_similarity < 1.0

    def test_address_edge_during_enabled_output_is_penalized(
        self, tmp_path: Path
    ) -> None:
        """Verify address chatter during active output lowers similarity so ghost-risk shows up."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture_csv(baseline_path, _build_capture_rows())
        _write_capture_csv(
            candidate_path, _build_capture_rows(active_address_glitch_row=2)
        )

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert candidate.active_address_edge_count > 0
        assert score.total < 0.95
        assert score.feature_scores["active_address_edge_count"] < 1.0

    def test_oe_duty_changes_reduce_similarity(self, tmp_path: Path) -> None:
        """Verify duration-based OE duty is included in electrical scoring."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture_csv(baseline_path, _build_capture_rows())
        _write_capture_csv(
            candidate_path, _build_capture_rows(oe_blank_padding_ticks=5)
        )

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert candidate.oe_active_fraction < baseline.oe_active_fraction
        assert "oe_median_blank_exceeds_5pct_active" in candidate.warnings
        assert score.feature_scores["oe_active_fraction"] < 1.0

    def test_oe_median_blank_absolute_warning_flags_large_blanks(
        self, tmp_path: Path
    ) -> None:
        """Verify median OE blank time has an absolute warning, not just a duty-ratio warning."""

        capture_path = tmp_path / "candidate.csv"
        _write_capture_csv(capture_path, _build_capture_rows(oe_blank_padding_ticks=50))

        summary = summarize_hub75_capture(load_hub75_logic_csv(capture_path), cols=4)

        assert summary.median_oe_blank_ns is not None
        assert summary.median_oe_blank_ns > 500.0
        assert "oe_median_blank_exceeds_500ns" in summary.warnings

    def test_oe_blank_outliers_are_summarized_and_penalized(
        self, tmp_path: Path
    ) -> None:
        """Verify rare OE-blank stalls are visible even when median blank stays stable."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture_csv(baseline_path, _build_capture_rows(rows=7))
        _write_capture_csv(
            candidate_path,
            _build_capture_rows(
                rows=7,
                long_oe_blank_rows=(1, 4),
                long_oe_blank_padding_ticks=600,
            ),
        )

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert baseline.long_oe_blank_count == 0
        assert candidate.long_oe_blank_count == 2
        assert candidate.median_long_oe_blank_period_intervals == pytest.approx(3.0)
        assert candidate.long_clk_period_count >= 2
        assert candidate.max_clk_period_ns is not None
        assert candidate.max_clk_period_ns > candidate.long_clk_period_threshold_ns
        assert candidate.max_oe_blank_ns is not None
        assert candidate.max_oe_blank_ns > candidate.long_oe_blank_threshold_ns
        assert score.feature_scores["max_oe_blank_ns"] < 1.0
        assert score.feature_scores["long_oe_blank_count"] < 1.0
        assert score.feature_scores["max_clk_period_ns"] < 1.0
        assert score.feature_scores["long_clk_period_count"] < 1.0

    def test_flatline_capture_scores_near_zero(self, tmp_path: Path) -> None:
        """Verify an electrically silent candidate cannot score like a plausible HUB75 waveform."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "flatline.csv"
        _write_capture_csv(baseline_path, _build_capture_rows())
        _write_capture_csv(candidate_path, _build_flatline_rows())

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert baseline.valid_hub75 is True
        assert candidate.valid_hub75 is False
        assert candidate.lat_rise_count == 0
        assert candidate.interval_count == 0
        assert "need_clock_activity" in candidate.validity_issues
        assert score.feature_scores["candidate_valid_hub75"] == 0.0
        assert score.feature_scores["validity_gate"] == 0.0
        assert score.total == 0.0

    def test_flatline_baseline_and_candidate_are_rejected(self, tmp_path: Path) -> None:
        """Verify dead-capture pairs cannot masquerade as a perfect electrical match."""

        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture_csv(baseline_path, _build_flatline_rows())
        _write_capture_csv(candidate_path, _build_flatline_rows())

        baseline = summarize_hub75_capture(load_hub75_logic_csv(baseline_path), cols=4)
        candidate = summarize_hub75_capture(
            load_hub75_logic_csv(candidate_path), cols=4
        )
        score = score_hub75_similarity(baseline, candidate)

        assert baseline.valid_hub75 is False
        assert candidate.valid_hub75 is False
        assert score.feature_scores["baseline_valid_hub75"] == 0.0
        assert score.feature_scores["candidate_valid_hub75"] == 0.0
        assert score.feature_scores["validity_gate"] == 0.0
        assert score.total == 0.0

    def test_capture_diagnosis_flags_unmapped_live_channels(
        self, tmp_path: Path
    ) -> None:
        """Verify live edges on unexpected channels are classified as a map mismatch."""

        capture_path = tmp_path / "shifted.csv"
        _write_capture_csv(
            capture_path,
            _shift_rows_to_columns(_build_capture_rows(), offset=8),
            headers=_shifted_headers(),
        )

        diagnosis = diagnose_hub75_capture(capture_path, cols=4)

        assert diagnosis.summary.valid_hub75 is False
        assert diagnosis.diagnosis == "possible_channel_map_mismatch"
        assert diagnosis.mapped_signal_edge_counts["CLK"] == 0
        assert diagnosis.active_channels[0].channel == 8
        assert diagnosis.active_channels[-1].channel == 13
        assert diagnosis.channel_activity[0].initial_level == 0
        assert diagnosis.channel_activity[-1].final_level == 0
        assert diagnosis.notes == (
            "expected_mapped_channels_flat",
            "unmapped_channels_show_activity",
        )

    def test_custom_signal_map_recovers_shifted_live_capture(
        self, tmp_path: Path
    ) -> None:
        """Verify alternate CLI mappings can score a shifted capture once channels are known."""

        capture_path = tmp_path / "shifted.csv"
        _write_capture_csv(
            capture_path,
            _shift_rows_to_columns(_build_capture_rows(), offset=8),
            headers=_shifted_headers(),
        )

        capture = load_hub75_logic_csv(
            capture_path,
            signal_map={
                "CLK": 8,
                "LAT": 9,
                "OE": 10,
                "A": 11,
                "B": 12,
                "C": 13,
                "D": 14,
                "E": 15,
            },
        )
        summary = summarize_hub75_capture(capture, cols=4)
        diagnosis = diagnose_hub75_capture(
            capture_path,
            signal_map={
                "CLK": 8,
                "LAT": 9,
                "OE": 10,
                "A": 11,
                "B": 12,
                "C": 13,
                "D": 14,
                "E": 15,
            },
            cols=4,
        )

        assert summary.valid_hub75 is True
        assert diagnosis.diagnosis == "valid_hub75"
        assert diagnosis.mapped_signal_edge_counts["CLK"] > 0
        assert diagnosis.active_channels[0].channel == 8
        assert diagnosis.active_channels[-1].channel == 13

    def test_capture_diagnosis_flags_global_flatline(self, tmp_path: Path) -> None:
        """Verify a capture with no edges anywhere is classified as electrically silent."""

        capture_path = tmp_path / "flatline.csv"
        _write_capture_csv(capture_path, _build_flatline_rows())

        diagnosis = diagnose_hub75_capture(capture_path, cols=4)

        assert diagnosis.summary.valid_hub75 is False
        assert diagnosis.diagnosis == "electrically_silent"
        assert diagnosis.active_channels == ()
        assert diagnosis.channel_activity[2].initial_level == 1
        assert diagnosis.channel_activity[2].final_level == 1
        assert diagnosis.notes == (
            "no_edges_on_any_captured_channel",
            "static_high_channels_present",
        )


def _write_capture_csv(
    path: Path,
    rows: list[tuple[float, list[int]]],
    *,
    headers: tuple[str, ...] = DEFAULT_HEADERS,
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for timestamp, state in rows:
            writer.writerow([f"{timestamp:.9f}", *state])


def _build_capture_rows(
    *,
    rows: int = 5,
    cols: int = 4,
    extra_clock_row: int | None = None,
    active_address_glitch_row: int | None = None,
    oe_blank_padding_ticks: int = 0,
    long_oe_blank_rows: tuple[int, ...] = (),
    long_oe_blank_padding_ticks: int = 0,
) -> list[tuple[float, list[int]]]:
    timestamp = 0.0
    state = [0, 0, 1, 0, 0, 0, 0, 0]
    samples: list[tuple[float, list[int]]] = [(timestamp, state.copy())]

    def emit(**changes: int) -> None:
        nonlocal timestamp
        timestamp += 20e-9
        for name, value in changes.items():
            state[_column_index(name)] = value
        samples.append((timestamp, state.copy()))

    for row in range(rows):
        emit(OE=1)
        for signal, value in _address_state(row).items():
            if state[_column_index(signal)] != value:
                emit(**{signal: value})
        clock_count = cols + (1 if extra_clock_row == row else 0)
        for _ in range(clock_count):
            emit(CLK=1)
            emit(CLK=0)
        emit(LAT=1)
        emit(LAT=0)
        emit(OE=0)
        if active_address_glitch_row == row:
            emit(A=1 - state[_column_index("A")])
            emit(A=1 - state[_column_index("A")])
        emit(OE=1)
        for _ in range(oe_blank_padding_ticks):
            emit()
        if row in long_oe_blank_rows:
            for _ in range(long_oe_blank_padding_ticks):
                emit()

    return samples


def _build_flatline_rows(*, samples: int = 8) -> list[tuple[float, list[int]]]:
    timestamp = 0.0
    state = [0, 0, 1, 0, 0, 0, 0, 0]
    capture_rows: list[tuple[float, list[int]]] = []
    for _ in range(samples):
        capture_rows.append((timestamp, state.copy()))
        timestamp += 20e-9
    return capture_rows


def _address_state(row: int) -> dict[str, int]:
    return {
        "A": (row >> 0) & 1,
        "B": (row >> 1) & 1,
        "C": (row >> 2) & 1,
        "D": (row >> 3) & 1,
        "E": (row >> 4) & 1,
    }


def _column_index(name: str) -> int:
    return DEFAULT_HEADERS.index(name) - 1


def _shifted_headers() -> tuple[str, ...]:
    return (
        "Time [s]",
        "X0",
        "X1",
        "X2",
        "X3",
        "X4",
        "X5",
        "X6",
        "X7",
        "CLK",
        "LAT",
        "OE",
        "A",
        "B",
        "C",
        "D",
        "E",
    )


def _shift_rows_to_columns(
    rows: list[tuple[float, list[int]]],
    *,
    offset: int,
) -> list[tuple[float, list[int]]]:
    shifted_rows: list[tuple[float, list[int]]] = []
    for timestamp, state in rows:
        shifted_state = [0] * offset + state
        shifted_rows.append((timestamp, shifted_state))
    return shifted_rows
