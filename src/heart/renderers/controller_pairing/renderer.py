from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import replace
from subprocess import TimeoutExpired
from typing import Iterable

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.controller_pairing.state import (
    ControllerPairingDeviceState, ControllerPairingState,
    ControllerPairingTarget)
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONTROLLER_TARGETS = (
    ControllerPairingTarget("1", "E4:17:D8:43:5C:48", "teal"),
    ControllerPairingTarget("2", "E4:17:D8:58:22:8A", "teal"),
    ControllerPairingTarget("3", "E4:17:D8:E9:76:C8", "pink"),
    ControllerPairingTarget("4", "E4:17:D8:91:15:35", "pink"),
)
DEFAULT_SCAN_SECONDS = 10.0
DEFAULT_CYCLE_DELAY_SECONDS = 2.0
DEFAULT_COMMAND_TIMEOUT_SECONDS = 20.0
INFO_LINE_PATTERN = re.compile(r"^\s*(?P<key>[A-Za-z]+):\s*(?P<value>.*)$")
SCAN_DEVICE_PATTERN = re.compile(
    r"(?:Device\s+)(?P<address>[0-9A-F:]{17})(?:\s+(?P<name>.*))?",
    re.IGNORECASE,
)
BACKGROUND_COLOR = (3, 5, 10)
TEXT_COLOR = (230, 235, 240)
PANEL_TEXT_COLOR = (255, 255, 255)
PANEL_MUTED_TEXT_COLOR = (20, 25, 32)
MUTED_COLOR = (120, 130, 145)
SCANNING_COLOR = (80, 180, 255)
PAIRED_COLOR = (255, 202, 88)
CONNECTED_COLOR = (95, 230, 150)
ERROR_COLOR = (255, 92, 92)
CONTROLLER_COLOR_SWATCHES = {
    "pink": (255, 105, 180),
    "teal": (0, 210, 190),
}
CONTROLLER_PANEL_COLORS = {
    "pink": (170, 34, 106),
    "teal": (0, 126, 118),
}
FONT_SIZE_PX = 14
SMALL_FONT_SIZE_PX = 12
PANEL_NUMBER_FONT_SIZE_PX = 28
PANEL_STATUS_FONT_SIZE_PX = 14
INPUT_LINE_COLOR = (245, 248, 255)
INPUT_ACTIVE_COLOR = (255, 232, 110)
INPUT_INACTIVE_COLOR = (155, 166, 180)
BUTTON_LABELS = {
    GamepadButton.SOUTH: "B",
    GamepadButton.EAST: "A",
    GamepadButton.WEST: "Y",
    GamepadButton.NORTH: "X",
    GamepadButton.PLUS: "+",
    GamepadButton.MINUS: "-",
    GamepadButton.HOME: "H",
    GamepadButton.CAPTURE: "C",
    GamepadButton.ZL: "ZL",
    GamepadButton.ZR: "ZR",
    GamepadButton.L3: "L3",
    GamepadButton.R3: "R3",
}


class BluetoothctlControllerPairer:
    def __init__(
        self,
        targets: Iterable[ControllerPairingTarget] = DEFAULT_CONTROLLER_TARGETS,
        *,
        scan_seconds: float = DEFAULT_SCAN_SECONDS,
        cycle_delay_seconds: float = DEFAULT_CYCLE_DELAY_SECONDS,
        command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        devices = tuple(
            ControllerPairingDeviceState(target=target) for target in targets
        )
        self._state = ControllerPairingState(devices=devices)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._scan_seconds = scan_seconds
        self._cycle_delay_seconds = cycle_delay_seconds
        self._command_timeout_seconds = command_timeout_seconds

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="heart-controller-pairing",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._update_state(scanning=False, last_message="stopped")

    def snapshot(self) -> ControllerPairingState:
        with self._lock:
            return self._state

    def _run(self) -> None:
        try:
            self._setup_adapter()
            self._refresh_known_devices()
            while not self._stop_event.is_set():
                self._refresh_known_devices()
                self._scan_once()
                self._pair_known_devices()
                if self._stop_event.wait(self._cycle_delay_seconds):
                    break
        except Exception:
            logger.exception("Controller pairing worker failed")
            self._update_state(scanning=False, last_message="worker failed")

    def _setup_adapter(self) -> None:
        self._update_state(last_message="preparing bluetooth")
        self._bluetoothctl("power", "on", timeout_seconds=5.0)
        self._bluetoothctl("pairable", "on", timeout_seconds=5.0)
        self._bluetoothctl("agent", "NoInputNoOutput", timeout_seconds=5.0)
        self._bluetoothctl("default-agent", timeout_seconds=5.0)

    def _scan_once(self) -> None:
        self._update_state(scanning=True, last_message="scanning")
        result = self._bluetoothctl(
            "scan",
            "on",
            timeout_seconds=self._scan_seconds + 2.0,
            bluetoothctl_timeout_seconds=self._scan_seconds,
        )
        self._bluetoothctl("scan", "off", timeout_seconds=5.0)
        discovered = self._parse_scan_output(result.output)
        for address, name in discovered.items():
            self._update_device(
                address,
                seen=True,
                name=name,
                last_action="seen",
                error=None,
            )
        self._update_state(
            scanning=False,
            cycle=self.snapshot().cycle + 1,
            last_message=f"scan found {len(discovered)} known",
        )

    def _pair_known_devices(self) -> None:
        for device in self.snapshot().devices:
            if self._stop_event.is_set():
                return
            self._refresh_info(device)
            current = self._device_state(device.target.address)
            if current is None:
                continue
            if not current.seen and not current.paired:
                continue
            if not current.paired:
                self._pair_device(current.target.address)
                self._refresh_info(current)
                current = self._device_state(current.target.address)
                if current is None or not current.paired:
                    continue
            if not current.trusted:
                self._trust_device(current.target.address)
                self._refresh_info(current)
                current = self._device_state(current.target.address)
                if current is None:
                    continue
            if not current.connected:
                self._connect_device(current.target.address)
                self._refresh_info(current)

    def _refresh_known_devices(self) -> None:
        for device in self.snapshot().devices:
            if self._stop_event.is_set():
                return
            self._refresh_info(device)

    def _pair_device(self, address: str) -> None:
        self._update_device(address, pairing=True, last_action="pairing", error=None)
        result = self._bluetoothctl(
            "pair",
            address,
            agent=True,
            timeout_seconds=self._command_timeout_seconds + 2.0,
            bluetoothctl_timeout_seconds=self._command_timeout_seconds,
        )
        self._update_device(
            address,
            pairing=False,
            last_action="paired" if result.returncode == 0 else "pair failed",
            error=None if result.returncode == 0 else _last_output_line(result.output),
        )

    def _trust_device(self, address: str) -> None:
        result = self._bluetoothctl("trust", address)
        self._update_device(
            address,
            last_action="trusted" if result.returncode == 0 else "trust failed",
            error=None if result.returncode == 0 else _last_output_line(result.output),
        )

    def _connect_device(self, address: str) -> None:
        result = self._bluetoothctl(
            "connect",
            address,
            timeout_seconds=self._command_timeout_seconds + 2.0,
            bluetoothctl_timeout_seconds=self._command_timeout_seconds,
        )
        self._update_device(
            address,
            last_action="connected" if result.returncode == 0 else "connect failed",
            error=None if result.returncode == 0 else _last_output_line(result.output),
        )

    def _refresh_info(self, device: ControllerPairingDeviceState) -> None:
        result = self._bluetoothctl("info", device.target.address, timeout_seconds=5.0)
        info = self._parse_info_output(result.output)
        if not info and "not available" in result.output:
            return
        self._update_device(device.target.address, **info)

    def _bluetoothctl(
        self,
        *args: str,
        agent: bool = False,
        timeout_seconds: float | None = None,
        bluetoothctl_timeout_seconds: float | None = None,
    ) -> "BluetoothctlResult":
        command = ["bluetoothctl"]
        if agent:
            command.extend(["--agent", "NoInputNoOutput"])
        if bluetoothctl_timeout_seconds is not None:
            command.extend(["--timeout", str(int(bluetoothctl_timeout_seconds))])
        command.extend(args)
        timeout = timeout_seconds or self._command_timeout_seconds
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return BluetoothctlResult(
                command=tuple(command),
                returncode=127,
                output="bluetoothctl not found",
            )
        except TimeoutExpired as exc:
            output = "\n".join(
                part
                for part in (
                    _decode_timeout_output(exc.stdout),
                    _decode_timeout_output(exc.stderr),
                    "bluetoothctl timed out",
                )
                if part
            )
            return BluetoothctlResult(
                command=tuple(command),
                returncode=124,
                output=output,
            )
        output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        ).strip()
        return BluetoothctlResult(
            command=tuple(command),
            returncode=result.returncode,
            output=output,
        )

    def _parse_scan_output(self, output: str) -> dict[str, str | None]:
        targets = {device.target.address.upper() for device in self.snapshot().devices}
        discovered: dict[str, str | None] = {}
        for line in output.splitlines():
            match = SCAN_DEVICE_PATTERN.search(line)
            if match is None:
                continue
            address = match.group("address").upper()
            if address not in targets:
                continue
            name = match.group("name")
            if name is not None:
                name = name.strip() or None
            discovered[address] = name
        return discovered

    def _parse_info_output(self, output: str) -> dict[str, object]:
        result: dict[str, object] = {}
        for line in output.splitlines():
            match = INFO_LINE_PATTERN.match(line)
            if match is None:
                continue
            key = match.group("key")
            value = match.group("value").strip()
            if key == "Name":
                result["name"] = value
            elif key == "Paired":
                result["paired"] = value.lower() == "yes"
            elif key == "Trusted":
                result["trusted"] = value.lower() == "yes"
            elif key == "Connected":
                result["connected"] = value.lower() == "yes"
        if result:
            result["error"] = None
        return result

    def _device_state(self, address: str) -> ControllerPairingDeviceState | None:
        normalized = address.upper()
        for device in self.snapshot().devices:
            if device.target.address.upper() == normalized:
                return device
        return None

    def _update_state(self, **changes: object) -> None:
        with self._lock:
            self._state = replace(self._state, **changes)

    def _update_device(self, address: str, **changes: object) -> None:
        normalized = address.upper()
        with self._lock:
            devices = tuple(
                replace(device, **changes)
                if device.target.address.upper() == normalized
                else device
                for device in self._state.devices
            )
            self._state = replace(self._state, devices=devices)


class BluetoothctlResult:
    def __init__(
        self,
        *,
        command: tuple[str, ...],
        returncode: int,
        output: str,
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output


class ControllerPairingRenderer(StatefulBaseRenderer[ControllerPairingState]):
    def __init__(
        self,
        targets: Iterable[ControllerPairingTarget] = DEFAULT_CONTROLLER_TARGETS,
    ) -> None:
        self._targets = tuple(targets)
        self._pairer: BluetoothctlControllerPairer | None = None
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        self._panel_number_font: pygame.font.Font | None = None
        self._panel_status_font: pygame.font.Font | None = None
        self._peripheral_manager: PeripheralManager | None = None
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ControllerPairingState:
        self._peripheral_manager = peripheral_manager
        return ControllerPairingState(
            devices=tuple(
                ControllerPairingDeviceState(target=target)
                for target in self._targets
            )
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        screen = window.screen
        if screen is None:
            return
        self._ensure_pairer_started()
        pairer = self._pairer
        if pairer is not None:
            self.set_state(pairer.snapshot())

        if not pygame.font.get_init():
            pygame.font.init()
        if self._font is None:
            self._font = pygame.font.Font(None, FONT_SIZE_PX)
        if self._small_font is None:
            self._small_font = pygame.font.Font(None, SMALL_FONT_SIZE_PX)
        if self._panel_number_font is None:
            self._panel_number_font = pygame.font.Font(
                None,
                PANEL_NUMBER_FONT_SIZE_PX,
            )
        if self._panel_status_font is None:
            self._panel_status_font = pygame.font.Font(
                None,
                PANEL_STATUS_FONT_SIZE_PX,
            )

        screen.fill(BACKGROUND_COLOR)
        self._draw_device_panels(screen)

    def reset(self) -> None:
        if self._pairer is not None:
            self._pairer.stop()
            self._pairer = None
        self._peripheral_manager = None
        super().reset()

    def _ensure_pairer_started(self) -> None:
        if self._pairer is None:
            logger.info("Starting controller pairing renderer worker")
            self._pairer = BluetoothctlControllerPairer(self._targets)
            self._pairer.start()

    def _draw_header(self, screen: pygame.Surface) -> None:
        if self._font is None:
            return
        paired_count = sum(1 for device in self.state.devices if device.paired)
        connected_count = sum(1 for device in self.state.devices if device.connected)
        scan_label = "scan" if self.state.scanning else "idle"
        label = (
            f"BT PAIR {paired_count}/{len(self.state.devices)} "
            f"paired {connected_count} con {scan_label}"
        )
        surface = self._font.render(label, True, TEXT_COLOR)
        screen.blit(surface, (4, 1))

    def _draw_device_panels(self, screen: pygame.Surface) -> None:
        if self._panel_number_font is None or self._panel_status_font is None:
            return
        devices = self.state.devices
        if not devices:
            return
        panel_width = max(1, screen.get_width() // len(devices))
        panel_height = screen.get_height()
        for index, device in enumerate(devices):
            x = index * panel_width
            width = (
                screen.get_width() - x
                if index == len(devices) - 1
                else panel_width
            )
            rect = pygame.Rect(x, 0, width, panel_height)
            base_color = CONTROLLER_PANEL_COLORS.get(
                device.target.color,
                BACKGROUND_COLOR,
            )
            pygame.draw.rect(screen, base_color, rect)
            snapshot = self._sample_gamepad_slot(index)

            self._draw_centered_text(
                screen,
                self._panel_number_font,
                device.target.label,
                pygame.Rect(x, 0, width, 18),
                PANEL_TEXT_COLOR,
            )
            self._draw_centered_text(
                screen,
                self._panel_status_font,
                device.target.color.upper(),
                pygame.Rect(x, 18, width, 8),
                PANEL_TEXT_COLOR,
            )
            self._draw_centered_text(
                screen,
                self._panel_status_font,
                _bluetooth_status_label(device),
                pygame.Rect(x, 26, width, 8),
                _bluetooth_status_color(device),
            )
            self._draw_centered_text(
                screen,
                self._panel_status_font,
                _input_status_label(index, snapshot),
                pygame.Rect(x, 34, width, 8),
                INPUT_ACTIVE_COLOR if snapshot.connected else INPUT_INACTIVE_COLOR,
            )
            self._draw_input_snapshot(
                screen,
                snapshot,
                pygame.Rect(x, 43, width, 21),
            )
        if screen.get_flags() & pygame.SRCALPHA:
            screen.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)

    def _draw_input_snapshot(
        self,
        screen: pygame.Surface,
        snapshot: GamepadSnapshot,
        rect: pygame.Rect,
    ) -> None:
        if self._small_font is None:
            return
        lines = _input_lines(snapshot)
        line_height = 7
        y = rect.top
        for line_index, line in enumerate(lines):
            color = INPUT_ACTIVE_COLOR if line_index == len(lines) - 1 else INPUT_LINE_COLOR
            self._draw_clipped_text(
                screen,
                self._small_font,
                line,
                pygame.Rect(rect.left + 2, y, max(1, rect.width - 4), line_height),
                color,
            )
            y += line_height

    def _sample_gamepad_slot(self, slot: int) -> GamepadSnapshot:
        manager = self._peripheral_manager
        if manager is None:
            return GamepadSnapshot(connected=False, identifier=None)
        return manager.input_io.gamepad.sample(
            joystick_id=slot,
            include_tapped_buttons=False,
        )

    def _draw_centered_text(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        rect: pygame.Rect,
        color: tuple[int, int, int],
    ) -> None:
        surface = font.render(text, True, color)
        text_rect = surface.get_rect(center=rect.center)
        screen.blit(surface, text_rect)

    def _draw_clipped_text(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        rect: pygame.Rect,
        color: tuple[int, int, int],
    ) -> None:
        previous_clip = screen.get_clip()
        screen.set_clip(rect)
        surface = font.render(text, True, color)
        screen.blit(surface, (rect.left, rect.top))
        screen.set_clip(previous_clip)


def _bluetooth_status_label(device: ControllerPairingDeviceState) -> str:
    if device.connected:
        return "BT LINK"
    if device.pairing:
        return "BT PAIR"
    if device.paired:
        return "BT SAVED"
    if device.seen:
        return "BT SEEN"
    if device.error:
        return "BT ERROR"
    return "BT WAIT"


def _bluetooth_status_color(device: ControllerPairingDeviceState) -> tuple[int, int, int]:
    if device.connected:
        return CONNECTED_COLOR
    if device.pairing or device.seen:
        return SCANNING_COLOR
    if device.paired:
        return PAIRED_COLOR
    if device.error:
        return ERROR_COLOR
    return MUTED_COLOR


def _input_status_label(slot: int, snapshot: GamepadSnapshot) -> str:
    if snapshot.connected:
        return f"APP SLOT {slot + 1}"
    return f"APP NO {slot + 1}"


def _input_lines(snapshot: GamepadSnapshot) -> tuple[str, str, str]:
    if not snapshot.connected:
        return ("input idle", "D 0,0", "B -")
    left_x = snapshot.axis_value(GamepadAxis.LEFT_X, dead_zone=0.0)
    left_y = snapshot.axis_value(GamepadAxis.LEFT_Y, dead_zone=0.0)
    right_x = snapshot.axis_value(GamepadAxis.RIGHT_X, dead_zone=0.0)
    right_y = snapshot.axis_value(GamepadAxis.RIGHT_Y, dead_zone=0.0)
    trigger_left = _trigger_pressure(
        snapshot.axis_value(GamepadAxis.TRIGGER_LEFT, dead_zone=0.0)
    )
    trigger_right = _trigger_pressure(
        snapshot.axis_value(GamepadAxis.TRIGGER_RIGHT, dead_zone=0.0)
    )
    buttons = _held_button_labels(snapshot)
    return (
        f"D {snapshot.dpad.x:+d},{snapshot.dpad.y:+d} L {_axis_pair(left_x, left_y)}",
        f"R {_axis_pair(right_x, right_y)} T {trigger_left:.1f}/{trigger_right:.1f}",
        f"B {buttons or '-'}",
    )


def _axis_pair(x: float, y: float) -> str:
    return f"{x:+.1f},{y:+.1f}"


def _trigger_pressure(raw_value: float) -> float:
    if raw_value < 0.0:
        return max(0.0, min(1.0, (raw_value + 1.0) * 0.5))
    return max(0.0, min(1.0, raw_value))


def _held_button_labels(snapshot: GamepadSnapshot) -> str:
    return " ".join(
        label
        for button, label in BUTTON_LABELS.items()
        if snapshot.button_held(button)
    )


def _short_address(address: str) -> str:
    return address[-8:]


def _compact_error(error: str) -> str:
    cleaned = " ".join(error.split())
    if len(cleaned) <= 18:
        return cleaned
    return f"{cleaned[:17]}..."


def _last_output_line(output: str) -> str | None:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1]


def _decode_timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
