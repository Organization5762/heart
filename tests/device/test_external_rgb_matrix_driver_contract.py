"""Compatibility contract for Heart's optional external RGB matrix runtime."""

from __future__ import annotations

import pytest

rgb_matrix = pytest.importorskip("heart_rgb_matrix_driver")


def test_external_driver_exposes_heart_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the pinned package provides every type used by Heart's adapter."""

    monkeypatch.setenv("HEART_PI5_MATRIX_BACKEND", "simulated")
    config = rgb_matrix.MatrixConfig(
        wiring=rgb_matrix.WiringProfile.Regular,
        panel_rows=64,
        panel_cols=64,
        chain_length=4,
        parallel=1,
        color_order=rgb_matrix.ColorOrder.RGB,
    )

    assert config.panel_rows == 64
    assert config.panel_cols == 64
    assert config.chain_length == 4
    assert config.parallel == 1
    driver = rgb_matrix.MatrixDriver(config)
    try:
        assert driver.width == 256
        assert driver.height == 64
        assert driver.stats().backend_name == "simulated"
    finally:
        driver.close()
