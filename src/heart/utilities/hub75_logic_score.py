"""HUB75 logic-capture scoring helpers for electrical regression checks."""

from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping, Sequence
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
OE_LONG_BLANK_THRESHOLD_NS = 10_000.0
OE_MEDIAN_BLANK_WARNING_NS = 500.0
OE_MEDIAN_BLANK_ACTIVE_FRACTION_WARNING = 0.05
CLK_LONG_PERIOD_THRESHOLD_NS = 10_000.0


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
        return self.initial_state[channel] ^ (
            bisect_right(self.edges[channel], timestamp) & 1
        )

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
    p99_clk_period_ns: float | None
    max_clk_period_ns: float | None
    p99_clk_high_ns: float | None
    max_clk_high_ns: float | None
    p99_clk_low_ns: float | None
    max_clk_low_ns: float | None
    long_clk_period_threshold_ns: float
    long_clk_period_count: int
    median_long_clk_period_intervals: float | None
    oe_active_fraction: float
    oe_blank_fraction: float
    median_oe_active_ns: float | None
    median_oe_blank_ns: float | None
    p90_oe_blank_ns: float | None
    p99_oe_blank_ns: float | None
    max_oe_blank_ns: float | None
    p90_oe_active_ns: float | None
    p99_oe_active_ns: float | None
    max_oe_active_ns: float | None
    long_oe_blank_threshold_ns: float
    long_oe_blank_count: int
    median_long_oe_blank_period_intervals: float | None
    address_edges_per_lat: dict[str, float]
    address_edge_counts: dict[str, int]
    p99_address_edge_interval_ns: dict[str, float | None]
    max_address_edge_interval_ns: dict[str, float | None]
    valid_hub75: bool
    validity_issues: tuple[str, ...]
    warnings: tuple[str, ...]


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
    edges: dict[int, list[float]] = {
        index: [] for index in range(column_count)
    }
    rises: dict[int, list[float]] = {
        index: [] for index in range(column_count)
    }
    falls: dict[int, list[float]] = {
        index: [] for index in range(column_count)
    }
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
                for channel, (old, new) in enumerate(
                    zip(previous_state, state, strict=True)
                ):
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
    address_edge_counts = _signal_edge_counts(capture, HUB75_ADDRESS_SIGNALS)
    address_edge_intervals = _signal_edge_intervals(capture, HUB75_ADDRESS_SIGNALS)
    clk_periods = [
        later - earlier
        for earlier, later in zip(clk_rises, clk_rises[1:], strict=False)
    ]
    clk_highs = _clock_high_durations(clk_rises, clk_falls)
    clk_lows = _clock_low_durations(clk_rises, clk_falls)
    long_clk_period_indexes = [
        index
        for index, duration in enumerate(clk_periods)
        if duration * 1_000_000_000.0 > CLK_LONG_PERIOD_THRESHOLD_NS
    ]
    long_clk_periods = [
        later - earlier
        for earlier, later in zip(
            long_clk_period_indexes,
            long_clk_period_indexes[1:],
            strict=False,
        )
    ]
    oe_durations = _level_durations(
        initial_level=capture.initial_state[capture.signal_map["OE"]],
        edges=capture.edges[capture.signal_map["OE"]],
        first_timestamp=capture.first_timestamp,
        last_timestamp=capture.last_timestamp,
    )
    oe_active_time = sum(oe_durations[0])
    oe_blank_time = sum(oe_durations[1])
    oe_total_time = oe_active_time + oe_blank_time
    long_oe_blank_indexes = [
        index
        for index, duration in enumerate(oe_durations[1])
        if duration * 1_000_000_000.0 > OE_LONG_BLANK_THRESHOLD_NS
    ]
    long_oe_blank_periods = [
        later - earlier
        for earlier, later in zip(
            long_oe_blank_indexes,
            long_oe_blank_indexes[1:],
            strict=False,
        )
    ]
    median_oe_active_ns = _median_ns(oe_durations[0])
    median_oe_blank_ns = _median_ns(oe_durations[1])
    validity_issues = _validate_hub75_summary(
        lat_rise_count=len(lat_rises),
        interval_count=len(intervals),
        median_clocks_per_row=float(median(clocks_per_row)) if clocks_per_row else 0.0,
        median_clk_period_ns=_median_ns(clk_periods),
    )
    warnings = _warn_hub75_summary(
        median_oe_active_ns=median_oe_active_ns,
        median_oe_blank_ns=median_oe_blank_ns,
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
        p99_clk_period_ns=_percentile_ns(clk_periods, 0.99),
        max_clk_period_ns=_max_ns(clk_periods),
        p99_clk_high_ns=_percentile_ns(clk_highs, 0.99),
        max_clk_high_ns=_max_ns(clk_highs),
        p99_clk_low_ns=_percentile_ns(clk_lows, 0.99),
        max_clk_low_ns=_max_ns(clk_lows),
        long_clk_period_threshold_ns=CLK_LONG_PERIOD_THRESHOLD_NS,
        long_clk_period_count=len(long_clk_period_indexes),
        median_long_clk_period_intervals=(
            float(median(long_clk_periods)) if long_clk_periods else None
        ),
        oe_active_fraction=oe_active_time / oe_total_time if oe_total_time else 0.0,
        oe_blank_fraction=oe_blank_time / oe_total_time if oe_total_time else 0.0,
        median_oe_active_ns=median_oe_active_ns,
        median_oe_blank_ns=median_oe_blank_ns,
        p90_oe_blank_ns=_percentile_ns(oe_durations[1], 0.90),
        p99_oe_blank_ns=_percentile_ns(oe_durations[1], 0.99),
        max_oe_blank_ns=_max_ns(oe_durations[1]),
        p90_oe_active_ns=_percentile_ns(oe_durations[0], 0.90),
        p99_oe_active_ns=_percentile_ns(oe_durations[0], 0.99),
        max_oe_active_ns=_max_ns(oe_durations[0]),
        long_oe_blank_threshold_ns=OE_LONG_BLANK_THRESHOLD_NS,
        long_oe_blank_count=len(long_oe_blank_indexes),
        median_long_oe_blank_period_intervals=(
            float(median(long_oe_blank_periods)) if long_oe_blank_periods else None
        ),
        address_edges_per_lat=address_edges_per_lat,
        address_edge_counts=address_edge_counts,
        p99_address_edge_interval_ns={
            signal: _percentile_ns(intervals, 0.99)
            for signal, intervals in address_edge_intervals.items()
        },
        max_address_edge_interval_ns={
            signal: _max_ns(intervals)
            for signal, intervals in address_edge_intervals.items()
        },
        valid_hub75=not validity_issues,
        validity_issues=validity_issues,
        warnings=warnings,
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
        activity
        for activity in active_channels
        if activity.channel not in mapped_channels
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
    """Return a capture-length-independent similarity between HUB75 waveforms."""

    control_scores = {
        "lat_rise_count": _activity_presence_similarity(
            baseline.lat_rise_count,
            candidate.lat_rise_count,
        ),
        "interval_count": _activity_presence_similarity(
            baseline.interval_count,
            candidate.interval_count,
        ),
        "row_clock_mismatch_count": _event_rate_similarity(
            baseline.row_clock_mismatch_count,
            baseline.interval_count,
            candidate.row_clock_mismatch_count,
            candidate.interval_count,
        ),
        "lat_while_output_enabled_count": _event_rate_similarity(
            baseline.lat_while_output_enabled_count,
            baseline.interval_count,
            candidate.lat_while_output_enabled_count,
            candidate.interval_count,
        ),
        "active_address_edge_count": _event_rate_similarity(
            baseline.active_address_edge_count,
            baseline.interval_count,
            candidate.active_address_edge_count,
            candidate.interval_count,
        ),
        "median_clocks_per_row": _relative_similarity(
            baseline.median_clocks_per_row,
            candidate.median_clocks_per_row,
            tolerance_fraction=0.02,
        ),
        "median_oe_active_fraction": _relative_similarity(
            _median_oe_active_fraction(baseline),
            _median_oe_active_fraction(candidate),
            tolerance_fraction=0.05,
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
        "p99_clk_period_ns": _relative_similarity(
            baseline.p99_clk_period_ns,
            candidate.p99_clk_period_ns,
            tolerance_fraction=0.25,
        ),
        "long_clk_period_count": _event_rate_similarity(
            baseline.long_clk_period_count,
            baseline.interval_count,
            candidate.long_clk_period_count,
            candidate.interval_count,
        ),
        "median_oe_active_ns": _relative_similarity(
            baseline.median_oe_active_ns,
            candidate.median_oe_active_ns,
            tolerance_fraction=0.25,
        ),
        "median_oe_blank_ns": _relative_similarity(
            baseline.median_oe_blank_ns,
            candidate.median_oe_blank_ns,
            tolerance_fraction=0.25,
        ),
        "p99_oe_blank_ns": _relative_similarity(
            baseline.p99_oe_blank_ns,
            candidate.p99_oe_blank_ns,
            tolerance_fraction=0.25,
        ),
        "long_oe_blank_count": _event_rate_similarity(
            baseline.long_oe_blank_count,
            baseline.interval_count,
            candidate.long_oe_blank_count,
            candidate.interval_count,
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
        control_similarity * 0.45 + timing_similarity * 0.35 + address_similarity * 0.20
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
                for channel, (old, new) in enumerate(
                    zip(previous_state, state, strict=True)
                ):
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
    return tuple(
        sorted(
            activities, key=lambda activity: (-activity.edge_count, activity.channel)
        )
    )


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


def _clock_high_durations(
    clk_rises: Sequence[float], clk_falls: Sequence[float]
) -> list[float]:
    durations: list[float] = []
    fall_index = 0
    for rise in clk_rises:
        while fall_index < len(clk_falls) and clk_falls[fall_index] < rise:
            fall_index += 1
        if fall_index < len(clk_falls):
            durations.append(clk_falls[fall_index] - rise)
    return durations


def _clock_low_durations(
    clk_rises: Sequence[float], clk_falls: Sequence[float]
) -> list[float]:
    durations: list[float] = []
    rise_index = 0
    for fall in clk_falls:
        while rise_index < len(clk_rises) and clk_rises[rise_index] < fall:
            rise_index += 1
        if rise_index < len(clk_rises):
            durations.append(clk_rises[rise_index] - fall)
    return durations


def _level_durations(
    *,
    initial_level: int,
    edges: Sequence[float],
    first_timestamp: float,
    last_timestamp: float,
) -> dict[int, list[float]]:
    durations: dict[int, list[float]] = {0: [], 1: []}
    level = initial_level
    run_start = first_timestamp
    for edge in edges:
        if edge > run_start:
            durations[level].append(edge - run_start)
        level ^= 1
        run_start = edge
    if last_timestamp > run_start:
        durations[level].append(last_timestamp - run_start)
    return durations


def _address_edges_per_lat(
    capture: Hub75LogicCapture,
    lat_rises: Sequence[float],
) -> dict[str, float]:
    if len(lat_rises) < 2:
        return {}
    interval_count = len(lat_rises) - 1
    ratios: dict[str, float] = {}
    for signal in HUB75_ADDRESS_SIGNALS:
        if signal not in capture.signal_map:
            continue
        channel = capture.signal_map[signal]
        ratios[signal] = (
            _count_between(capture.edges[channel], lat_rises[0], lat_rises[-1])
            / interval_count
        )
    return ratios


def _signal_edge_counts(
    capture: Hub75LogicCapture,
    signals: Sequence[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in signals:
        if signal not in capture.signal_map:
            continue
        counts[signal] = len(capture.edges[capture.signal_map[signal]])
    return counts


def _signal_edge_intervals(
    capture: Hub75LogicCapture,
    signals: Sequence[str],
) -> dict[str, list[float]]:
    intervals: dict[str, list[float]] = {}
    for signal in signals:
        if signal not in capture.signal_map:
            continue
        edges = capture.edges[capture.signal_map[signal]]
        intervals[signal] = [
            later - earlier for earlier, later in zip(edges, edges[1:], strict=False)
        ]
    return intervals


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


def _percentile_ns(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * percentile)
    return sorted_values[index] * 1_000_000_000.0


def _max_ns(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return max(values) * 1_000_000_000.0


def _activity_presence_similarity(baseline: int, candidate: int) -> float:
    return 1.0 if (baseline > 0) == (candidate > 0) else 0.0


def _median_oe_active_fraction(summary: Hub75SignalSummary) -> float | None:
    active = summary.median_oe_active_ns
    blank = summary.median_oe_blank_ns
    if active is None or blank is None or active + blank <= 0:
        return None
    return active / (active + blank)


def _event_rate_similarity(
    baseline_count: int,
    baseline_opportunities: int,
    candidate_count: int,
    candidate_opportunities: int,
) -> float:
    baseline_rate = (
        baseline_count / baseline_opportunities
        if baseline_opportunities > 0
        else None
    )
    candidate_rate = (
        candidate_count / candidate_opportunities
        if candidate_opportunities > 0
        else None
    )
    return _relative_similarity(
        baseline_rate,
        candidate_rate,
        tolerance_fraction=0.05,
    )


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


def _average(values: Iterable[float]) -> float:
    resolved = tuple(values)
    if not resolved:
        return 1.0
    return sum(resolved) / len(resolved)


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


def _warn_hub75_summary(
    *,
    median_oe_active_ns: float | None,
    median_oe_blank_ns: float | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if median_oe_blank_ns is None:
        return ()
    if median_oe_blank_ns > OE_MEDIAN_BLANK_WARNING_NS:
        warnings.append("oe_median_blank_exceeds_500ns")
    if (
        median_oe_active_ns is not None
        and median_oe_active_ns > 0
        and median_oe_blank_ns / median_oe_active_ns
        > OE_MEDIAN_BLANK_ACTIVE_FRACTION_WARNING
    ):
        warnings.append("oe_median_blank_exceeds_5pct_active")
    return tuple(warnings)
