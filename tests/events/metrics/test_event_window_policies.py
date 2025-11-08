"""Tests covering :class:`EventWindow` and associated policies."""


import pytest

from heart.events.metrics import (EventSample, EventWindow, MaxAgePolicy,
                                  MaxLengthPolicy, combine_windows)


def test_max_length_policy_requires_positive_count() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        MaxLengthPolicy(count=0)


def test_max_age_policy_requires_positive_window() -> None:
    with pytest.raises(ValueError, match="positive duration"):
        MaxAgePolicy(window=0.0)


def test_event_window_applies_max_length_policy() -> None:
    window = EventWindow[str](policies=(MaxLengthPolicy(count=2),))

    window.append("a", timestamp=0.0)
    window.append("b", timestamp=1.0)
    window.append("c", timestamp=2.0)

    assert window.values() == ("b", "c")


def test_event_window_applies_max_age_policy() -> None:
    window = EventWindow[str](policies=(MaxAgePolicy(window=1.5),))

    window.append("a", timestamp=0.0)
    window.append("b", timestamp=0.5)
    window.append("c", timestamp=2.0)

    assert window.values() == ("c",)


def test_event_window_iterates_values_in_order() -> None:
    window = EventWindow[str](policies=(MaxLengthPolicy(count=3),))
    for index in range(3):
        window.append(f"event-{index}", timestamp=float(index))

    assert list(window) == ["event-0", "event-1", "event-2"]


def test_event_window_samples_return_dataclasses() -> None:
    window = EventWindow[str](policies=(MaxLengthPolicy(count=2),))
    window.extend(["a", "b"], timestamp=1.0, step=0.25)

    samples = window.samples()
    assert samples == (
        EventSample(value="a", timestamp=1.0),
        EventSample(value="b", timestamp=1.25),
    )


def test_event_window_derive_appends_additional_policies() -> None:
    base = EventWindow[str](policies=(MaxLengthPolicy(count=3),))
    derived = base.derive(MaxAgePolicy(window=2.0))

    timestamps = (0.0, 0.5, 1.0, 2.5, 3.0)
    for index, ts in enumerate(timestamps):
        derived.append(f"event-{index}", timestamp=ts)

    assert derived.values() == ("event-3", "event-4")


def test_combine_windows_merges_policies() -> None:
    recent = EventWindow[str](policies=(MaxLengthPolicy(count=2),))
    young = EventWindow[str](policies=(MaxAgePolicy(window=3.0),))

    combined = combine_windows(recent, young)
    helper = EventWindow[str](policies=(*recent.policies, *young.policies))

    for timestamp, value in enumerate(("a", "b", "c", "d")):
        combined.append(value, timestamp=float(timestamp))
        helper.append(value, timestamp=float(timestamp))

    assert combined.values() == helper.values()