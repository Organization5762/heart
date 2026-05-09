from __future__ import annotations

from types import SimpleNamespace

from heart.peripheral.gamepad.gamepad import (
    BLUETOOTH_RECONNECT_INTERVAL_SECONDS,
    DEFAULT_BLUETOOTH_GAMEPAD_MACS,
    Gamepad,
)


class TestGamepadBluetoothReconnect:
    def test_default_bluetooth_gamepad_macs_include_known_controllers(
        self,
    ) -> None:
        assert DEFAULT_BLUETOOTH_GAMEPAD_MACS == (
            "E4:17:D8:37:C3:40",
            "E4:17:D8:37:FE:88",
            "E4:17:D8:E9:76:C8",
            "E4:17:D8:E9:99:B3",
        )

    def test_reconnect_attempts_each_known_bluetooth_gamepad_with_bluetoothctl(
        self,
        monkeypatch,
    ) -> None:
        attempted: list[str] = []
        gamepad = Gamepad()

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Gamepad.gamepad_detected",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Configuration.is_pi",
            lambda: True,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.shutil.which",
            lambda command: (
                "/usr/bin/bluetoothctl" if command == "bluetoothctl" else None
            ),
        )

        def fake_run(args, *, capture_output, text, timeout):
            attempted.append(" ".join(args))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.subprocess.run",
            fake_run,
        )

        gamepad._read_from_gamepad(interval=0)

        assert attempted == [
            f"bluetoothctl connect {mac_address}"
            for mac_address in DEFAULT_BLUETOOTH_GAMEPAD_MACS
        ]

    def test_reconnect_uses_blueutil_when_bluetoothctl_is_unavailable(
        self,
        monkeypatch,
    ) -> None:
        attempted: list[str] = []
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.shutil.which",
            lambda command: (
                "/opt/homebrew/bin/blueutil" if command == "blueutil" else None
            ),
        )

        def fake_run(args, *, capture_output, text, timeout):
            attempted.append(" ".join(args))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.subprocess.run",
            fake_run,
        )

        Gamepad()._connect_bluetooth_gamepads()

        assert attempted == [
            f"blueutil --connect {mac_address}"
            for mac_address in DEFAULT_BLUETOOTH_GAMEPAD_MACS
        ]

    def test_reconnect_noops_when_no_bluetooth_connector_is_available(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.shutil.which",
            lambda command: None,
        )

        def fake_run(args, *, capture_output, text, timeout):
            raise AssertionError("subprocess.run should not be called")

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.subprocess.run",
            fake_run,
        )

        Gamepad()._connect_bluetooth_gamepads()

    def test_pi_reconnect_attempts_are_rate_limited(
        self,
        monkeypatch,
    ) -> None:
        attempted: list[str] = []
        gamepad = Gamepad()

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Gamepad.gamepad_detected",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Configuration.is_pi",
            lambda: True,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.shutil.which",
            lambda command: (
                "/usr/bin/bluetoothctl" if command == "bluetoothctl" else None
            ),
        )

        clock = iter(
            [
                10.0,
                10.0 + BLUETOOTH_RECONNECT_INTERVAL_SECONDS - 0.1,
                10.0 + BLUETOOTH_RECONNECT_INTERVAL_SECONDS,
            ]
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.time.monotonic",
            lambda: next(clock),
        )

        def fake_run(args, *, capture_output, text, timeout):
            attempted.append(" ".join(args))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.subprocess.run",
            fake_run,
        )

        gamepad._read_from_gamepad(interval=0)
        gamepad._read_from_gamepad(interval=1)
        gamepad._read_from_gamepad(interval=2)

        expected_attempts = [
            f"bluetoothctl connect {mac_address}"
            for mac_address in DEFAULT_BLUETOOTH_GAMEPAD_MACS
        ]
        assert attempted == [*expected_attempts, *expected_attempts]

    def test_non_pi_does_not_auto_connect_bluetooth_gamepads(
        self,
        monkeypatch,
    ) -> None:
        attempted: list[str] = []
        gamepad = Gamepad()

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Gamepad.gamepad_detected",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.Configuration.is_pi",
            lambda: False,
        )

        def fake_run(args, *, capture_output, text, timeout):
            attempted.append(" ".join(args))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.subprocess.run",
            fake_run,
        )

        gamepad._read_from_gamepad(interval=0)

        assert attempted == []
