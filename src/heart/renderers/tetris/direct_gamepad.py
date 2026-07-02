from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadDpadValue)
from heart.peripheral.core.input.gamepad import DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
from heart.peripheral.gamepad.gamepad import GamepadIdentifier
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth,
                                                          DpadType,
                                                          SwitchLikeMapping,
                                                          SwitchProMapping)
from heart.peripheral.gamepad.screen_mapping import (
    bluetooth_mac_for_screen_slot, normalize_bluetooth_mac)
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
LINUX_JOYSTICK_SYSFS = Path("/sys/class/input")
STICK_LOG_THRESHOLD = 0.35


@dataclass(frozen=True, slots=True)
class DirectGamepadSnapshot:
    connected: bool
    identifier: str | None
    buttons: dict[GamepadButton, bool] = field(default_factory=dict)
    tapped_buttons: frozenset[GamepadButton] = frozenset()
    axes: dict[GamepadAxis, float] = field(default_factory=dict)
    dpad: GamepadDpadValue = GamepadDpadValue()
    timestamp_monotonic: float = 0.0
    slot: int = 0

    def button_held(self, button: GamepadButton) -> bool:
        return self.buttons.get(button, False)

    def button_tapped(self, button: GamepadButton) -> bool:
        return button in self.tapped_buttons

    def axis_value(
        self,
        axis: GamepadAxis,
        *,
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> float:
        value = self.axes.get(axis, 0.0)
        if abs(value) < dead_zone:
            return 0.0
        return value


class DirectTetrisGamepads:
    def __init__(self) -> None:
        self._joysticks_by_slot: dict[int, pygame.joystick.JoystickType] = {}
        self._previous_buttons_by_slot: dict[int, dict[GamepadButton, bool]] = {}
        self._snapshots_by_slot: dict[int, DirectGamepadSnapshot] = {}
        self._last_logged_signature_by_slot: dict[int, tuple[object, ...]] = {}
        self._joystick_initialized = False

    def refresh(self, player_count: int) -> None:
        self._ensure_initialized()
        pygame.event.pump()
        for slot in range(player_count):
            self._snapshots_by_slot[slot] = self._read_slot(slot)

    def snapshot_for_slot(self, slot: int) -> DirectGamepadSnapshot:
        snapshot = self._snapshots_by_slot.get(slot)
        if snapshot is not None:
            return snapshot
        return DirectGamepadSnapshot(
            connected=False,
            identifier=None,
            timestamp_monotonic=time.monotonic(),
            slot=slot,
        )

    def _ensure_initialized(self) -> None:
        if self._joystick_initialized:
            return
        pygame.joystick.init()
        self._joystick_initialized = True

    def _read_slot(self, slot: int) -> DirectGamepadSnapshot:
        joystick = self._joystick_for_slot(slot)
        if joystick is None:
            return DirectGamepadSnapshot(
                connected=False,
                identifier=None,
                timestamp_monotonic=time.monotonic(),
                slot=slot,
            )
        mapping = _mapping_for_joystick(joystick)
        buttons = _read_buttons(joystick, mapping)
        previous = self._previous_buttons_by_slot.get(slot, {})
        tapped_buttons = frozenset(
            button
            for button, held in buttons.items()
            if held and not previous.get(button)
        )
        self._previous_buttons_by_slot[slot] = buttons
        snapshot = DirectGamepadSnapshot(
            connected=True,
            identifier=joystick.get_name(),
            buttons=buttons,
            tapped_buttons=tapped_buttons,
            axes=_read_axes(joystick, mapping),
            dpad=_read_dpad(joystick, mapping),
            timestamp_monotonic=time.monotonic(),
            slot=slot,
        )
        self._log_snapshot(snapshot)
        return snapshot

    def _joystick_for_slot(
        self,
        slot: int,
    ) -> pygame.joystick.JoystickType | None:
        joystick = self._joysticks_by_slot.get(slot)
        if joystick is not None and _slot_detected(slot):
            return joystick
        if joystick is not None:
            _safe_quit(joystick)
            self._joysticks_by_slot.pop(slot, None)
            self._previous_buttons_by_slot.pop(slot, None)
            logger.info("tetris.direct_gamepad.disconnected slot=%s", slot)

        physical_index = _physical_joystick_index(slot)
        if physical_index is None:
            return None
        try:
            joystick = pygame.joystick.Joystick(physical_index)
            joystick.init()
        except pygame.error as exc:
            logger.warning(
                "tetris.direct_gamepad.connect_failed slot=%s physical_index=%s error=%s",
                slot,
                physical_index,
                exc,
            )
            return None
        self._joysticks_by_slot[slot] = joystick
        logger.info(
            "tetris.direct_gamepad.ready slot=%s physical_index=%s name=%s",
            slot,
            physical_index,
            joystick.get_name(),
        )
        return joystick

    def _log_snapshot(self, snapshot: DirectGamepadSnapshot) -> None:
        signature = _snapshot_signature(snapshot)
        if signature == self._last_logged_signature_by_slot.get(snapshot.slot):
            return
        self._last_logged_signature_by_slot[snapshot.slot] = signature
        if not signature:
            return
        logger.info(
            "tetris.direct_gamepad.input slot=%s id=%s dpad=(%s,%s) left=(%.2f,%.2f) tapped=%s held=%s",
            snapshot.slot,
            snapshot.identifier,
            snapshot.dpad.x,
            snapshot.dpad.y,
            snapshot.axes.get(GamepadAxis.LEFT_X, 0.0),
            snapshot.axes.get(GamepadAxis.LEFT_Y, 0.0),
            ",".join(
                button.value
                for button in sorted(
                    snapshot.tapped_buttons, key=lambda item: item.value
                )
            ),
            ",".join(
                button.value
                for button, held in sorted(
                    snapshot.buttons.items(),
                    key=lambda item: item[0].value,
                )
                if held
            ),
        )


def _slot_detected(slot: int) -> bool:
    if Configuration.is_pi():
        if _target_bluetooth_mac(slot) is None:
            return False
        return _mapped_joystick_index(slot) is not None
    return pygame.joystick.get_count() > slot


def _physical_joystick_index(slot: int) -> int | None:
    if Configuration.is_pi():
        return _mapped_joystick_index(slot)
    if pygame.joystick.get_count() <= slot:
        return None
    return slot


def _mapped_joystick_index(slot: int) -> int | None:
    target_mac = _target_bluetooth_mac(slot)
    if target_mac is None:
        return None
    normalized_target = _normalize_bluetooth_mac(target_mac)
    for pygame_index, joystick_path in enumerate(
        sorted(LINUX_JOYSTICK_SYSFS.glob("js*"))
    ):
        uniq_path = joystick_path / "device" / "uniq"
        try:
            controller_mac = uniq_path.read_text().strip()
        except OSError:
            continue
        if _normalize_bluetooth_mac(controller_mac) != normalized_target:
            continue
        return pygame_index
    return None


def _target_bluetooth_mac(slot: int) -> str | None:
    return bluetooth_mac_for_screen_slot(slot)


def _normalize_bluetooth_mac(mac_address: str) -> str:
    return normalize_bluetooth_mac(mac_address)


def _mapping_for_joystick(joystick: pygame.joystick.JoystickType) -> SwitchLikeMapping:
    try:
        identifier = GamepadIdentifier(joystick.get_name())
    except ValueError:
        identifier = GamepadIdentifier.BIT_DO_LITE_2
    if identifier is GamepadIdentifier.SWITCH_PRO:
        return SwitchProMapping()
    if Configuration.is_pi():
        return BitDoLite2Bluetooth()
    return BitDoLite2()


def _read_buttons(
    joystick: pygame.joystick.JoystickType,
    mapping: SwitchLikeMapping,
) -> dict[GamepadButton, bool]:
    return {
        GamepadButton.SOUTH: _button_held(joystick, mapping.BUTTON_B),
        GamepadButton.EAST: _button_held(joystick, mapping.BUTTON_A),
        GamepadButton.WEST: _button_held(joystick, mapping.BUTTON_Y),
        GamepadButton.NORTH: _button_held(joystick, mapping.BUTTON_X),
        GamepadButton.PLUS: _button_held(joystick, mapping.BUTTON_PLUS),
        GamepadButton.MINUS: _button_held(joystick, mapping.BUTTON_MINUS),
        GamepadButton.HOME: _button_held(joystick, mapping.BUTTON_HOME),
        GamepadButton.CAPTURE: _button_held(joystick, mapping.BUTTON_CAPTURE),
        GamepadButton.ZL: _button_held(joystick, mapping.BUTTON_ZL),
        GamepadButton.ZR: _button_held(joystick, mapping.BUTTON_ZR),
        GamepadButton.L3: _button_held(joystick, mapping.BUTTON_L3),
        GamepadButton.R3: _button_held(joystick, mapping.BUTTON_R3),
    }


def _read_axes(
    joystick: pygame.joystick.JoystickType,
    mapping: SwitchLikeMapping,
) -> dict[GamepadAxis, float]:
    return {
        GamepadAxis.LEFT_X: _axis_value(joystick, mapping.AXIS_LEFT_X),
        GamepadAxis.LEFT_Y: _axis_value(joystick, mapping.AXIS_LEFT_Y),
        GamepadAxis.RIGHT_X: _axis_value(joystick, mapping.AXIS_RIGHT_X),
        GamepadAxis.RIGHT_Y: _axis_value(joystick, mapping.AXIS_RIGHT_Y),
        GamepadAxis.TRIGGER_LEFT: _axis_value(joystick, mapping.AXIS_L),
        GamepadAxis.TRIGGER_RIGHT: _axis_value(joystick, mapping.AXIS_R),
    }


def _read_dpad(
    joystick: pygame.joystick.JoystickType,
    mapping: SwitchLikeMapping,
) -> GamepadDpadValue:
    if mapping.get_dpad_type() is DpadType.HAT:
        hat_index = mapping.DPAD_HAT
        if hat_index is None or hat_index < 0:
            return GamepadDpadValue()
        try:
            x_dir, y_dir = joystick.get_hat(hat_index)
        except pygame.error:
            return GamepadDpadValue()
        return GamepadDpadValue(x=int(x_dir), y=int(y_dir))
    if mapping.get_dpad_type() is DpadType.BUTTONS:
        x_dir = int(_button_held(joystick, mapping.DPAD_RIGHT)) - int(
            _button_held(joystick, mapping.DPAD_LEFT)
        )
        y_dir = int(_button_held(joystick, mapping.DPAD_UP)) - int(
            _button_held(joystick, mapping.DPAD_DOWN)
        )
        return GamepadDpadValue(x=x_dir, y=y_dir)
    return GamepadDpadValue()


def _button_held(
    joystick: pygame.joystick.JoystickType,
    button_id: int | None,
) -> bool:
    if button_id is None or button_id < 0 or button_id >= joystick.get_numbuttons():
        return False
    return bool(joystick.get_button(button_id))


def _axis_value(
    joystick: pygame.joystick.JoystickType,
    axis_id: int | None,
) -> float:
    if axis_id is None or axis_id < 0 or axis_id >= joystick.get_numaxes():
        return 0.0
    return float(joystick.get_axis(axis_id))


def _safe_quit(joystick: pygame.joystick.JoystickType) -> None:
    try:
        joystick.quit()
    except pygame.error:
        return


def _snapshot_signature(snapshot: DirectGamepadSnapshot) -> tuple[object, ...]:
    left_x = snapshot.axes.get(GamepadAxis.LEFT_X, 0.0)
    left_y = snapshot.axes.get(GamepadAxis.LEFT_Y, 0.0)
    axis_x = round(left_x, 2) if abs(left_x) >= STICK_LOG_THRESHOLD else 0.0
    axis_y = round(left_y, 2) if abs(left_y) >= STICK_LOG_THRESHOLD else 0.0
    held_buttons = tuple(
        sorted(button.value for button, held in snapshot.buttons.items() if held)
    )
    tapped_buttons = tuple(sorted(button.value for button in snapshot.tapped_buttons))
    if (
        snapshot.dpad.x == 0
        and snapshot.dpad.y == 0
        and axis_x == 0.0
        and axis_y == 0.0
        and not held_buttons
        and not tapped_buttons
    ):
        return ()
    return (
        snapshot.dpad.x,
        snapshot.dpad.y,
        axis_x,
        axis_y,
        held_buttons,
        tapped_buttons,
    )
