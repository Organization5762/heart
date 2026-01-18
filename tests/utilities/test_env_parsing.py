"""Tests for env parsing helpers."""

from __future__ import annotations

import pytest

from heart.utilities.env.parsing import (
    _env_flag,
    _env_float,
    _env_int,
    _env_optional_int,
)


class TestEnvParsingHelpers:
    """Group env parsing helper tests so configuration parsing stays predictable across deployments."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("true", True),
            ("  YES ", True),
            ("1", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("off", False),
        ],
    )
    def test_env_flag_recognizes_truthy_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
        expected: bool,
    ) -> None:
        """Confirm _env_flag recognizes truthy tokens while keeping falsy defaults predictable for feature flags."""
        monkeypatch.setenv("HEART_TEST_FLAG", value)

        assert _env_flag("HEART_TEST_FLAG") is expected

    def test_env_flag_returns_default_when_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure _env_flag returns its default when unset so optional flags stay stable without configuration."""
        monkeypatch.delenv("HEART_TEST_FLAG", raising=False)

        assert _env_flag("HEART_TEST_FLAG", default=True) is True

    def test_env_int_enforces_minimum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify _env_int rejects values below the minimum so misconfiguration is surfaced early."""
        monkeypatch.setenv("HEART_TEST_INT", "2")

        with pytest.raises(ValueError):
            _env_int("HEART_TEST_INT", default=0, minimum=3)

    def test_env_optional_int_returns_none_when_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Check _env_optional_int returns None when unset so callers can distinguish absence from zero."""
        monkeypatch.delenv("HEART_TEST_OPTIONAL_INT", raising=False)

        assert _env_optional_int("HEART_TEST_OPTIONAL_INT") is None

    def test_env_float_enforces_bounds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Confirm _env_float enforces min/max bounds so tuning values stay within safe limits."""
        monkeypatch.setenv("HEART_TEST_FLOAT", "1.5")

        with pytest.raises(ValueError):
            _env_float("HEART_TEST_FLOAT", default=0.5, minimum=2.0, maximum=3.0)

        with pytest.raises(ValueError):
            _env_float("HEART_TEST_FLOAT", default=0.5, minimum=0.0, maximum=1.0)
