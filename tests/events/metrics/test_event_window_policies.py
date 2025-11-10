"""Tests covering :class:`EventWindow` and associated policies."""

from __future__ import annotations

import pytest

from heart.events.metrics import (EventSample, EventWindow, MaxAgePolicy,
                                  MaxLengthPolicy, combine_windows)


class TestEventsMetricsEventWindowPolicies:
    """Group Events Metrics Event Window Policies tests so events metrics event window policies behaviour stays reliable. This preserves confidence in events metrics event window policies for end-to-end scenarios."""

    def test_max_length_policy_requires_positive_count(self) -> None:
        """Verify that MaxLengthPolicy raises when constructed with a non-positive count. This protects against misconfiguration that would otherwise produce unbounded buffers."""
        with pytest.raises(ValueError, match="positive integer"):
            MaxLengthPolicy(count=0)



    def test_max_age_policy_requires_positive_window(self) -> None:
        """Verify that MaxAgePolicy raises when the configured window duration is not positive. This prevents nonsensical windows that could hide stale telemetry."""
        with pytest.raises(ValueError, match="positive duration"):
            MaxAgePolicy(window=0.0)



    def test_event_window_applies_max_length_policy(self) -> None:
        """Verify that EventWindow discards oldest entries to honour the max-length policy. This keeps memory usage predictable during spikes in event volume."""
        window = EventWindow[str](policies=(MaxLengthPolicy(count=2),))

        window.append("a", timestamp=0.0)
        window.append("b", timestamp=1.0)
        window.append("c", timestamp=2.0)

        assert window.values() == ("b", "c")



    def test_event_window_applies_max_age_policy(self) -> None:
        """Verify that EventWindow excludes entries older than the configured age window. This ensures time-based analyses focus on the freshest data."""
        window = EventWindow[str](policies=(MaxAgePolicy(window=1.5),))

        window.append("a", timestamp=0.0)
        window.append("b", timestamp=0.5)
        window.append("c", timestamp=2.0)

        assert window.values() == ("c",)



    def test_event_window_iterates_values_in_order(self) -> None:
        """Verify that iterating an EventWindow yields values in the order they were appended. This preserves chronological semantics for consumers that assume FIFO ordering."""
        window = EventWindow[str](policies=(MaxLengthPolicy(count=3),))
        for index in range(3):
            window.append(f"event-{index}", timestamp=float(index))

        assert list(window) == ["event-0", "event-1", "event-2"]



    def test_event_window_samples_return_dataclasses(self) -> None:
        """Verify that EventWindow.samples returns EventSample objects with derived timestamps. This provides structured records so downstream consumers can reconstruct event timing."""
        window = EventWindow[str](policies=(MaxLengthPolicy(count=2),))
        window.extend(["a", "b"], timestamp=1.0, step=0.25)

        samples = window.samples()
        assert samples == (
            EventSample(value="a", timestamp=1.0),
            EventSample(value="b", timestamp=1.25),
        )



    def test_event_window_derive_appends_additional_policies(self) -> None:
        """Verify that derive creates a new window evaluating the original and added policies together. This makes policy composition predictable for complex retention strategies."""
        base = EventWindow[str](policies=(MaxLengthPolicy(count=3),))
        derived = base.derive(MaxAgePolicy(window=2.0))

        timestamps = (0.0, 0.5, 1.0, 2.5, 3.0)
        for index, ts in enumerate(timestamps):
            derived.append(f"event-{index}", timestamp=ts)

        assert derived.values() == ("event-3", "event-4")



    def test_combine_windows_merges_policies(self) -> None:
        """Verify that combine_windows produces a window enforcing the policies from both inputs. This ensures merged analytics honour all constraints when aggregating sources."""
        recent = EventWindow[str](policies=(MaxLengthPolicy(count=2),))
        young = EventWindow[str](policies=(MaxAgePolicy(window=3.0),))

        combined = combine_windows(recent, young)
        helper = EventWindow[str](policies=(*recent.policies, *young.policies))

        for timestamp, value in enumerate(("a", "b", "c", "d")):
            combined.append(value, timestamp=float(timestamp))
            helper.append(value, timestamp=float(timestamp))

        assert combined.values() == helper.values()
