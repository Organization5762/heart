"""HUB75 logic-capture scoring helpers for electrical regression checks."""

from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median

REQUIRED_SIGNALS = ("CLK", "LAT", "OE", "A", "B", "C", "D")
OPTIONAL_SIGNALS = ("E",)
DEFAULT_SIGNAL_MAP = {
    "CLK": 0,
    "LAT": 1,
    "OE": 2,
    "A": 3,
    "B": 4,
    "C": 5,
    "D": 6,
    "E": 7,
}
HUB75_ADDRESS_SIGNALS = ("A", "B", "C", "D", "E")


@dataclass(frozen=True)
class Hub75LogicCapture:
    """Raw edge lists derived from a Logic digital CSV export."""

    signal_map: dict[str, int]
    initial_state: list[int]
    rises: dict[int, list[float]]
    falls: dict[int, list[float]]
    edges: dict[int, list[float]]
    sample_count: int
    first_timestamp: float
    last_timestamp: float

    def level_at(self, signal: str, timestamp: float) -> int:
        """Return the logical level for a signal at a given timestamp."""

        channel = self.signal_map[signal]
        return self.initial_state[channel] ^ (bisect_right(self.edges[channel], timestamp) & 1)

    def edge_count_between(self, signal: str, start: float, end: float) -> int:
        """Return the number of edges for a signal between two timestamps."""

        channel = self.signal_map[signal]
        return _count_between(self.edges[channel], start, end)


@dataclass(frozen=True)
class LogicChannelActivity:
    """Per-channel edge summary for whole-capture diagnostics."""

    channel: int
    edge_count: int
    rise_count: int
    fall_count: int
    initial_level: int
    final_level: int


@dataclass(frozen=True)
class Hub75SignalSummary:
    """Condensed timing and ordering metrics for one capture."""

    sample_count: int
    span_seconds: float
    lat_rise_count: int
    interval_count: int
    median_clocks_per_row: float
    row_clock_mismatch_count: int
    lat_while_output_enabled_count: int
    active_address_edge_count: int
    median_clk_period_ns: float | None
    median_clk_high_ns: float | None
    median_clk_low_ns: float | None
    address_edges_per_lat: dict[str, float]
    valid_hub75: bool
    validity_issues: tuple[str, ...]


@dataclass(frozen=True)
class Hub75SimilarityScore:
    """Normalized 0..1 comparison between a baseline and candidate capture."""

    total: float
    control_similarity: float
    timing_similarity: float
    address_similarity: float
    feature_scores: dict[str, float]


@dataclass(frozen=True)
class Hub75CaptureDiagnosis:
    """Explain whether an invalid capture looks silent or mis-mapped."""

    summary: Hub75SignalSummary
    diagnosis: str
    channel_activity: tuple[LogicChannelActivity, ...]
    active_channels: tuple[LogicChannelActivity, ...]
    mapped_signal_edge_counts: dict[str, int]
    notes: tuple[str, ...]


def load_hub75_logic_csv(
    path: str | Path,
    signal_map: Mapping[str, int] | None = None,
) -> Hub75LogicCapture:
    """Load a Saleae raw digital CSV export into edge lists."""

    resolved_map = _resolve_signal_map(signal_map)
    column_count = max(resolved_map.values()) + 1
    edges = {index: [] for index in range(column_count)}
    rises = {index: [] for index in range(column_count)}
    falls = {index: [] for index in range(column_count)}
    initial_state: list[int] | None = None
    sample_count = 0
    first_timestamp = 0.0
    last_timestamp = 0.0

    with Path(path).open(newline="") as handle:
        rows = csv.reader(handle)
        next(rows)
        previous_state: list[int] | None = None
        for row in rows:
            timestamp = float(row[0])
            state = [int(value) for value in row[1 : 1 + column_count]]
            if initial_state is None:
                initial_state = state.copy()
                first_timestamp = timestamp
            if previous_state is not None:
                for channel, (old, new) in enumerate(zip(previous_state, state, strict=True)):
                    if old == new:
                        continue
                    edges[channel].append(timestamp)
                    if new:
                        rises[channel].append(timestamp)
                    else:
                        falls[channel].append(timestamp)
            previous_state = state
            last_timestamp = timestamp
            sample_count += 1

    if initial_state is None:
        msg = f"{path}: empty HUB75 logic CSV"
        raise ValueError(msg)

    return Hub75LogicCapture(
        signal_map=resolved_map,
        initial_state=initial_state,
        rises=rises,
        falls=falls,
        edges=edges,
        sample_count=sample_count,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
    )


def summarize_hub75_capture(
    capture: Hub75LogicCapture,
    *,
    cols: int = 64,
) -> Hub75SignalSummary:
    """Extract the key Hub75 timing and ordering metrics from one capture."""

    clk_rises = capture.rises[capture.signal_map["CLK"]]
    clk_falls = capture.falls[capture.signal_map["CLK"]]
    lat_rises = capture.rises[capture.signal_map["LAT"]]
    oe_rises = capture.rises[capture.signal_map["OE"]]
    oe_falls = capture.falls[capture.signal_map["OE"]]
    intervals = list(zip(lat_rises, lat_rises[1:], strict=False))
    clocks_per_row: list[int] = []
    lat_while_output_enabled_count = 0
    active_address_edge_count = 0

    for start, end in intervals:
        clocks = _count_between(clk_rises, start, end)
        clocks_per_row.append(clocks)
        if capture.level_at("OE", start) == 0:
            lat_while_output_enabled_count += 1
        active_address_edge_count += _count_address_edges_while_output_enabled(
            capture,
            start,
            end,
            oe_falls,
            oe_rises,
        )

    row_clock_mismatch_count = sum(1 for count in clocks_per_row if count != cols)
    address_edges_per_lat = _address_edges_per_lat(capture, lat_rises)
    clk_periods = [later - earlier for earlier, later in zip(clk_rises, clk_rises[1:], strict=False)]
    clk_highs = _clock_high_durations(clk_rises, clk_falls)
    clk_lows = _clock_low_durations(clk_rises, clk_falls)
    validity_issues = _validate_hub75_summary(
        lat_rise_count=len(lat_rises),
        interval_count=len(intervals),
        median_clocks_per_row=float(median(clocks_per_row)) if clocks_per_row else 0.0,
        median_clk_period_ns=_median_ns(clk_periods),
    )

    return Hub75SignalSummary(
        sample_count=capture.sample_count,
        span_seconds=capture.last_timestamp - capture.first_timestamp,
        lat_rise_count=len(lat_rises),
        interval_count=len(intervals),
        median_clocks_per_row=float(median(clocks_per_row)) if clocks_per_row else 0.0,
        row_clock_mismatch_count=row_clock_mismatch_count,
        lat_while_output_enabled_count=lat_while_output_enabled_count,
        active_address_edge_count=active_address_edge_count,
        median_clk_period_ns=_median_ns(clk_periods),
        median_clk_high_ns=_median_ns(clk_highs),
        median_clk_low_ns=_median_ns(clk_lows),
        address_edges_per_lat=address_edges_per_lat,
        valid_hub75=not validity_issues,
        validity_issues=validity_issues,
    )


def diagnose_hub75_capture(
    path: str | Path,
    *,
    signal_map: Mapping[str, int] | None = None,
    cols: int = 64,
) -> Hub75CaptureDiagnosis:
    """Classify whether a capture is valid, silent, or likely channel-mismapped."""

    capture = load_hub75_logic_csv(path, signal_map)
    summary = summarize_hub75_capture(capture, cols=cols)
    all_channel_activity = summarize_logic_channels(path)
    mapped_edge_counts = {
        signal: len(capture.edges[channel])
        for signal, channel in capture.signal_map.items()
    }
    active_channels = tuple(
        activity for activity in all_channel_activity if activity.edge_count > 0
    )

    if summary.valid_hub75:
        return Hub75CaptureDiagnosis(
            summary=summary,
            diagnosis="valid_hub75",
            channel_activity=all_channel_activity,
            active_channels=active_channels,
            mapped_signal_edge_counts=mapped_edge_counts,
            notes=(),
        )

    mapped_channels = set(capture.signal_map.values())
    unexpected_active_channels = tuple(
        activity for activity in active_channels if activity.channel not in mapped_channels
    )
    mapped_edge_total = sum(mapped_edge_counts.values())
    if mapped_edge_total == 0 and unexpected_active_channels:
        return Hub75CaptureDiagnosis(
            summary=summary,
            diagnosis="possible_channel_map_mismatch",
            channel_activity=all_channel_activity,
            active_channels=active_channels,
            mapped_signal_edge_counts=mapped_edge_counts,
            notes=(
                "expected_mapped_channels_flat",
                "unmapped_channels_show_activity",
            ),
        )
    if not active_channels:
        static_high_channels = tuple(
            activity.channel
            for activity in all_channel_activity
            if activity.initial_level == 1 and activity.final_level == 1
        )
        notes = ["no_edges_on_any_captured_channel"]
        if static_high_channels:
            notes.append("static_high_channels_present")
        return Hub75CaptureDiagnosis(
            summary=summary,
            diagnosis="electrically_silent",
            channel_activity=all_channel_activity,
            active_channels=(),
            mapped_signal_edge_counts=mapped_edge_counts,
            notes=tuple(notes),
        )
    return Hub75CaptureDiagnosis(
        summary=summary,
        diagnosis="invalid_hub75_waveform",
        channel_activity=all_channel_activity,
        active_channels=active_channels,
        mapped_signal_edge_counts=mapped_edge_counts,
        notes=summary.validity_issues,
    )


def score_hub75_similarity(
    baseline: Hub75SignalSummary,
    candidate: Hub75SignalSummary,
) -> Hub75SimilarityScore:
    """Return a normalized similarity score between two Hub75 captures."""

    row_activity_similarity = min(
        _count_similarity(baseline.lat_rise_count, candidate.lat_rise_count),
        _count_similarity(baseline.interval_count, candidate.interval_count),
    )
    control_scores = {
        "lat_rise_count": _count_similarity(
            baseline.lat_rise_count,
            candidate.lat_rise_count,
        ),
        "interval_count": _count_similarity(
            baseline.interval_count,
            candidate.interval_count,
        ),
        "row_clock_mismatch_count": row_activity_similarity * _count_similarity(
            baseline.row_clock_mismatch_count,
            candidate.row_clock_mismatch_count,
        ),
        "lat_while_output_enabled_count": row_activity_similarity * _count_similarity(
            baseline.lat_while_output_enabled_count,
            candidate.lat_while_output_enabled_count,
        ),
        "active_address_edge_count": row_activity_similarity * _count_similarity(
            baseline.active_address_edge_count,
            candidate.active_address_edge_count,
        ),
        "median_clocks_per_row": row_activity_similarity * _relative_similarity(
            baseline.median_clocks_per_row,
            candidate.median_clocks_per_row,
            tolerance_fraction=0.02,
        ),
    }
    timing_scores = {
        "median_clk_period_ns": _relative_similarity(
            baseline.median_clk_period_ns,
            candidate.median_clk_period_ns,
            tolerance_fraction=0.10,
        ),
        "median_clk_high_ns": _relative_similarity(
            baseline.median_clk_high_ns,
            candidate.median_clk_high_ns,
            tolerance_fraction=0.20,
        ),
        "median_clk_low_ns": _relative_similarity(
            baseline.median_clk_low_ns,
            candidate.median_clk_low_ns,
            tolerance_fraction=0.20,
        ),
    }
    address_scores = {
        f"address_edges_per_lat_{signal.lower()}": _relative_similarity(
            baseline.address_edges_per_lat.get(signal),
            candidate.address_edges_per_lat.get(signal),
            tolerance_fraction=0.25,
        )
        for signal in baseline.address_edges_per_lat
    }
    feature_scores = {
        **control_scores,
        **timing_scores,
        **address_scores,
        "baseline_valid_hub75": 1.0 if baseline.valid_hub75 else 0.0,
        "candidate_valid_hub75": 1.0 if candidate.valid_hub75 else 0.0,
    }
    validity_gate = 1.0 if baseline.valid_hub75 and candidate.valid_hub75 else 0.0
    feature_scores["validity_gate"] = validity_gate
    control_similarity = _average(control_scores.values()) * validity_gate
    timing_similarity = _average(timing_scores.values()) * validity_gate
    address_similarity = _average(address_scores.values()) * validity_gate
    total = (
        control_similarity * 0.45
        + timing_similarity * 0.35
        + address_similarity * 0.20
    )
    return Hub75SimilarityScore(
        total=total,
        control_similarity=control_similarity,
        timing_similarity=timing_similarity,
        address_similarity=address_similarity,
        feature_scores=feature_scores,
    )


def score_hub75_capture_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    signal_map: Mapping[str, int] | None = None,
    cols: int = 64,
) -> tuple[Hub75SignalSummary, Hub75SignalSummary, Hub75SimilarityScore]:
    """Load two CSV captures, summarize them, and return their similarity."""

    baseline_capture = load_hub75_logic_csv(baseline_path, signal_map)
    candidate_capture = load_hub75_logic_csv(candidate_path, signal_map)
    baseline_summary = summarize_hub75_capture(baseline_capture, cols=cols)
    candidate_summary = summarize_hub75_capture(candidate_capture, cols=cols)
    score = score_hub75_similarity(baseline_summary, candidate_summary)
    return baseline_summary, candidate_summary, score


def summarize_logic_channels(path: str | Path) -> tuple[LogicChannelActivity, ...]:
    """Return edge counts for every captured CSV column, regardless of mapping."""

    activities: list[LogicChannelActivity] = []
    with Path(path).open(newline="") as handle:
        rows = csv.reader(handle)
        header = next(rows)
        channel_count = len(header) - 1
        initial_state: list[int] | None = None
        final_state: list[int] | None = None
        previous_state: list[int] | None = None
        edges = [0] * channel_count
        rises = [0] * channel_count
        falls = [0] * channel_count
        for row in rows:
            state = [int(value) for value in row[1 : 1 + channel_count]]
            if initial_state is None:
                initial_state = state.copy()
            if previous_state is not None:
                for channel, (old, new) in enumerate(zip(previous_state, state, strict=True)):
                    if old == new:
                        continue
                    edges[channel] += 1
                    if new:
                        rises[channel] += 1
                    else:
                        falls[channel] += 1
            previous_state = state
            final_state = state.copy()

    if initial_state is None or final_state is None:
        msg = f"{path}: empty HUB75 logic CSV"
        raise ValueError(msg)

    for channel in range(channel_count):
        activities.append(
            LogicChannelActivity(
                channel=channel,
                edge_count=edges[channel],
                rise_count=rises[channel],
                fall_count=falls[channel],
                initial_level=initial_state[channel],
                final_level=final_state[channel],
            )
        )
    return tuple(sorted(activities, key=lambda activity: (-activity.edge_count, activity.channel)))


def _resolve_signal_map(
    signal_map: Mapping[str, int] | None,
) -> dict[str, int]:
    resolved = {name: DEFAULT_SIGNAL_MAP[name] for name in REQUIRED_SIGNALS}
    if signal_map is not None:
        for name, channel in signal_map.items():
            resolved[name.upper()] = channel
    missing = [name for name in REQUIRED_SIGNALS if name not in resolved]
    if missing:
        msg = f"missing required HUB75 signals: {', '.join(missing)}"
        raise ValueError(msg)
    for optional in OPTIONAL_SIGNALS:
        if signal_map is None:
            resolved.setdefault(optional, DEFAULT_SIGNAL_MAP[optional])
    return resolved


def _count_between(values: Sequence[float], start: float, end: float) -> int:
    return bisect_left(values, end) - bisect_right(values, start)


def _slice_between(values: Sequence[float], start: float, end: float) -> list[float]:
    begin = bisect_right(values, start)
    finish = bisect_left(values, end)
    return list(values[begin:finish])


def _clock_high_durations(clk_rises: Sequence[float], clk_falls: Sequence[float]) -> list[float]:
    durations: list[float] = []
    fall_index = 0
    for rise in clk_rises:
        while fall_index < len(clk_falls) and clk_falls[fall_index] < rise:
            fall_index += 1
        if fall_index < len(clk_falls):
            durations.append(clk_falls[fall_index] - rise)
    return durations


def _clock_low_durations(clk_rises: Sequence[float], clk_falls: Sequence[float]) -> list[float]:
    durations: list[float] = []
    rise_index = 0
    for fall in clk_falls:
        while rise_index < len(clk_rises) and clk_rises[rise_index] < fall:
            rise_index += 1
        if rise_index < len(clk_rises):
            durations.append(clk_rises[rise_index] - fall)
    return durations


def _address_edges_per_lat(
    capture: Hub75LogicCapture,
    lat_rises: Sequence[float],
) -> dict[str, float]:
    if not lat_rises:
        return {}
    lat_edge_count = len(lat_rises)
    ratios: dict[str, float] = {}
    for signal in HUB75_ADDRESS_SIGNALS:
        if signal not in capture.signal_map:
            continue
        channel = capture.signal_map[signal]
        ratios[signal] = len(capture.edges[channel]) / lat_edge_count
    return ratios


def _count_address_edges_while_output_enabled(
    capture: Hub75LogicCapture,
    start: float,
    end: float,
    oe_falls: Sequence[float],
    oe_rises: Sequence[float],
) -> int:
    count = 0
    windows: list[tuple[float, float]] = []
    if capture.level_at("OE", start) == 0:
        first_rise_after_start = next((rise for rise in oe_rises if rise > start), end)
        windows.append((start, min(first_rise_after_start, end)))
    for fall in _slice_between(oe_falls, start, end):
        first_rise_after_fall = next((rise for rise in oe_rises if rise > fall), end)
        windows.append((fall, min(first_rise_after_fall, end)))
    for signal in HUB75_ADDRESS_SIGNALS:
        if signal not in capture.signal_map:
            continue
        for window_start, window_end in windows:
            count += capture.edge_count_between(signal, window_start, window_end)
    return count


def _median_ns(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return median(values) * 1_000_000_000.0


def _count_similarity(baseline: int, candidate: int) -> float:
    if baseline == candidate:
        return 1.0
    if baseline == 0:
        return 1.0 / (1.0 + candidate)
    return max(0.0, 1.0 - abs(candidate - baseline) / max(baseline, candidate, 1))


def _relative_similarity(
    baseline: float | None,
    candidate: float | None,
    *,
    tolerance_fraction: float,
) -> float:
    if baseline is None or candidate is None:
        return 1.0 if baseline is candidate else 0.0
    if baseline == candidate:
        return 1.0
    scale = max(abs(baseline), 1e-9) * tolerance_fraction
    return max(0.0, 1.0 - abs(candidate - baseline) / scale)


def _average(values: Sequence[float]) -> float:
    if not values:
        return 1.0
    return sum(values) / len(values)


def _validate_hub75_summary(
    *,
    lat_rise_count: int,
    interval_count: int,
    median_clocks_per_row: float,
    median_clk_period_ns: float | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    if lat_rise_count < 2:
        issues.append("need_at_least_two_lat_edges")
    if interval_count < 1:
        issues.append("need_at_least_one_row_interval")
    if median_clocks_per_row <= 0.0:
        issues.append("need_clock_activity")
    if median_clk_period_ns is None:
        issues.append("need_clk_period")
    return tuple(issues)
