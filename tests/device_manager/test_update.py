from heart_device_manager.driver_update.modes import UpdateMode
from heart_device_manager.update import resolve_update_mode


class TestHeartDeviceManagerUpdate:
    """Cover top-level update mode selection so CLI requests consistently choose the intended flashing workflow."""

    def test_resolve_update_mode_prefers_config_default_for_auto(self):
        """Verify auto mode defers to the driver configuration so drivers can opt into Arduino flashing without extra CLI flags."""
        assert (
            resolve_update_mode(
                requested_mode=UpdateMode.AUTO,
                config_default=UpdateMode.ARDUINO,
            )
            == UpdateMode.ARDUINO
        )

    def test_resolve_update_mode_honors_explicit_override(self):
        """Verify explicit mode requests win over driver defaults so operators can still force the CircuitPython path for debugging."""
        assert (
            resolve_update_mode(
                requested_mode=UpdateMode.CIRCUITPYTHON,
                config_default=UpdateMode.ARDUINO,
            )
            == UpdateMode.CIRCUITPYTHON
        )
