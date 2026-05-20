from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadDpadValue, GamepadSnapshot)
from heart.renderers.controller_pairing.renderer import (
    _bluetooth_status_label, _input_lines, _input_status_label)
from heart.renderers.controller_pairing.state import (
    ControllerPairingDeviceState, ControllerPairingTarget)


class TestControllerPairingRenderer:
    def test_input_lines_show_live_gamepad_state(self) -> None:
        snapshot = GamepadSnapshot(
            connected=True,
            identifier="8BitDo Lite 2",
            buttons={
                GamepadButton.SOUTH: True,
                GamepadButton.ZR: True,
            },
            axes={
                GamepadAxis.LEFT_X: 0.25,
                GamepadAxis.LEFT_Y: -0.75,
                GamepadAxis.RIGHT_X: -0.5,
                GamepadAxis.RIGHT_Y: 0.125,
                GamepadAxis.TRIGGER_LEFT: -0.5,
                GamepadAxis.TRIGGER_RIGHT: 0.8,
            },
            dpad=GamepadDpadValue(x=1, y=-1),
        )

        assert _input_lines(snapshot) == (
            "D +1,-1 L +0.2,-0.8",
            "R -0.5,+0.1 T 0.2/0.8",
            "B B ZR",
        )

    def test_input_lines_show_idle_slot(self) -> None:
        assert _input_lines(GamepadSnapshot(connected=False, identifier=None)) == (
            "input idle",
            "D 0,0",
            "B -",
        )

    def test_status_labels_separate_bluetooth_and_app_input(self) -> None:
        target = ControllerPairingTarget("1", "E4:17:D8:43:5C:48", "teal")
        device = ControllerPairingDeviceState(target=target, connected=True)

        assert _bluetooth_status_label(device) == "BT LINK"
        assert _input_status_label(
            0,
            GamepadSnapshot(connected=False, identifier=None),
        ) == "APP NO 1"
        assert _input_status_label(
            0,
            GamepadSnapshot(connected=True, identifier="8BitDo Lite 2"),
        ) == "APP SLOT 1"
