from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import final

import numpy as np
import pygame

from heart.device import Cube, Device, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.display.color import Color
from heart.navigation import ComposedRenderer, GameModes, MultiScene
from heart.peripheral.core.input import (GamepadButton, GamepadDpadValue,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.sensor import Acceleration
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color import RenderColor
from heart.renderers.pixels.renderer import Border
from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.renderer import Tixyland
from heart.renderers.water_cube.provider import WaterCubeStateProvider
from heart.renderers.water_cube.renderer import WaterCube
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.testing.state_similarity import (StateSimilarityAction,
                                            StateSimilarityScenario)

_KEY_CODES = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "down": pygame.K_DOWN,
    "up": pygame.K_UP,
}
_GAMEPAD_BUTTONS = {button.value: button for button in GamepadButton}
_SWITCH_PRO_AXES = {
    "trigger_left": 4,
    "trigger_right": 5,
}
_SWITCH_PRO_BUTTONS = {
    "zl": 9,
    "zr": 10,
}
_EMPTY_KEYBOARD = KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)


def build_state_similarity_workflow(
    scenario: StateSimilarityScenario,
    *,
    device: Device | None = None,
) -> StateSimilarityWorkflow:
    """Build a replayable real Heart workflow for a serialized scenario."""

    if scenario.initial.config is None:
        raise ValueError(f"Scenario {scenario.name!r} requires initial.config")
    config = _mapping(scenario.initial.config, label="initial.config")
    if scenario.kind == "game_modes":
        return _build_game_modes_workflow(
            scenario,
            config,
            device=device or _navigation_device(config),
        )
    if scenario.kind == "multi_scene":
        return _build_multi_scene_workflow(
            scenario,
            config,
            device=device or _navigation_device(config),
        )
    if scenario.kind == "scene_controller":
        return _build_scene_controller_workflow(scenario, config)
    raise ValueError(f"Unsupported state-similarity scenario kind {scenario.kind!r}")


@final
@dataclass(frozen=True)
class StateSimilarityTransition:
    """Serializable progress for an active renderer transition."""

    fraction: float
    sliding: bool


@final
class StateSimilarityWorkflow:
    """Replay actions and inspect state, frames, and transitions for one scenario."""

    def __init__(
        self,
        *,
        scenario: StateSimilarityScenario,
        execute_action: Callable[[StateSimilarityAction], None],
        project_state: Callable[[], object],
        render: Callable[[], pygame.Surface],
        cleanup: Callable[[], None],
        advance_frame: Callable[[float], None],
        transition_progress: Callable[[], StateSimilarityTransition | None],
    ) -> None:
        self.scenario = scenario
        self._execute_action = execute_action
        self._project_state = project_state
        self._render = render
        self._cleanup = cleanup
        self._advance_frame = advance_frame
        self._transition_progress = transition_progress
        self._is_cleaned_up = False

    def execute_action(self, action: StateSimilarityAction) -> None:
        self._ensure_active()
        self._execute_action(action)

    def project_state(self) -> object:
        self._ensure_active()
        return self._project_state()

    def render(self) -> pygame.Surface:
        self._ensure_active()
        return self._render()

    def cleanup(self) -> None:
        if self._is_cleaned_up:
            return
        self._cleanup()
        self._is_cleaned_up = True

    def advance_frame(self, delta_ms: float) -> None:
        self._ensure_active()
        if (
            isinstance(delta_ms, bool)
            or not isinstance(delta_ms, int | float)
            or not math.isfinite(delta_ms)
            or delta_ms < 0
        ):
            raise ValueError("delta_ms must be a finite non-negative number")
        self._advance_frame(float(delta_ms))

    def transition_progress(self) -> StateSimilarityTransition | None:
        self._ensure_active()
        return self._transition_progress()

    def _ensure_active(self) -> None:
        if self._is_cleaned_up:
            raise RuntimeError(
                f"State-similarity workflow {self.scenario.name!r} is cleaned up"
            )


@final
class _FrameClock:
    def __init__(self, delta_ms: float) -> None:
        self._delta_ms = delta_ms

    def get_fps(self) -> float:
        return 60.0

    def get_time(self) -> float:
        return self._delta_ms


@final
class _VirtualJoystick:
    """Mutable pygame joystick boundary for ordered controller workflows."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._axes: dict[int, float] = {}
        self._buttons: dict[int, bool] = {}

    def set_input(
        self,
        *,
        axes: Mapping[int, float],
        buttons: Mapping[int, bool],
    ) -> None:
        self._axes = dict(axes)
        self._buttons = dict(buttons)

    def get_name(self) -> str:
        return self._name

    def get_numbuttons(self) -> int:
        return 16

    def get_numaxes(self) -> int:
        return 6

    def get_button(self, button_id: int) -> bool:
        return self._buttons.get(button_id, False)

    def get_axis(self, axis_id: int) -> float:
        return self._axes.get(axis_id, 0.0)

    def get_hat(self, _hat_id: int) -> tuple[int, int]:
        return (0, 0)

    def quit(self) -> None:
        pass


@final
@dataclass
class _FixedDevice(Device):
    width: int
    height: int

    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)


def _build_game_modes_workflow(
    scenario: StateSimilarityScenario,
    config: Mapping[str, object],
    *,
    device: Device,
) -> StateSimilarityWorkflow:
    peripheral_manager = PeripheralManager()
    runtime = PeripheralRuntime(peripheral_manager)
    game_modes = GameModes()
    modes = _sequence(config["modes"], label="config.modes")
    for index, value in enumerate(modes):
        mode_config = _mapping(value, label=f"config.modes[{index}]")
        mode = game_modes.add_mode(
            RenderColor(
                _color(mode_config["title_rgb"], label=f"config.modes[{index}].title_rgb")
            ),
            name=_string(mode_config["name"], label=f"config.modes[{index}].name"),
        )
        for renderer in _build_navigation_renderers(
            mode_config,
            legacy_rgb_key="rgb",
            label=f"config.modes[{index}]",
        ):
            mode.add_renderer(renderer)

    window = DisplayContext(
        device=device,
        screen=pygame.display.set_mode(device.full_display_size()),
        clock=pygame.time.Clock(),
    )
    game_modes.initialize(
        window=window,
        peripheral_manager=peripheral_manager,
        orientation=device.orientation,
    )
    return StateSimilarityWorkflow(
        scenario=scenario,
        execute_action=lambda action: _execute_navigation_action(runtime, action),
        project_state=game_modes.snapshot_state,
        render=lambda: _render_navigation(
            game_modes.get_renderers(),
            peripheral_manager,
            window,
            device,
        ),
        cleanup=lambda: _cleanup_renderer(game_modes, peripheral_manager),
        advance_frame=lambda delta_ms: _advance_frame(peripheral_manager, delta_ms),
        transition_progress=lambda: _game_modes_transition(game_modes),
    )


def _build_multi_scene_workflow(
    scenario: StateSimilarityScenario,
    config: Mapping[str, object],
    *,
    device: Device,
) -> StateSimilarityWorkflow:
    peripheral_manager = PeripheralManager()
    runtime = PeripheralRuntime(peripheral_manager)
    scenes = _sequence(config["scenes"], label="config.scenes")
    multi_scene = MultiScene(
        [
            _compose_navigation_scene(
                _build_navigation_renderers(
                    _mapping(value, label=f"config.scenes[{index}]"),
                    legacy_rgb_key="rgb",
                    label=f"config.scenes[{index}]",
                )
            )
            for index, value in enumerate(scenes)
        ],
        enable_dpad_scene_selection=_boolean(
            config["enable_dpad_scene_selection"],
            label="config.enable_dpad_scene_selection",
        ),
    )
    window = _window(device)
    multi_scene.initialize(
        window=window,
        peripheral_manager=peripheral_manager,
        orientation=device.orientation,
    )
    return StateSimilarityWorkflow(
        scenario=scenario,
        execute_action=lambda action: _execute_navigation_action(runtime, action),
        project_state=multi_scene.snapshot_state,
        render=lambda: _render_navigation(
            multi_scene.get_renderers(),
            peripheral_manager,
            window,
            device,
        ),
        cleanup=lambda: _cleanup_renderer(multi_scene, peripheral_manager),
        advance_frame=lambda delta_ms: _advance_frame(peripheral_manager, delta_ms),
        transition_progress=lambda: None,
    )


def _build_scene_controller_workflow(
    scenario: StateSimilarityScenario,
    config: Mapping[str, object],
) -> StateSimilarityWorkflow:
    device = _build_device(_mapping(config["device"], label="config.device"))
    gamepad_config = _mapping(config["gamepad"], label="config.gamepad")
    manager, joystick = _manager_with_gamepad(
        _string(gamepad_config["name"], label="config.gamepad.name")
    )
    renderer = _build_scene_renderer(config, device=device, manager=manager)
    window = _window(device)
    renderer.initialize(window, manager, device.orientation)
    return StateSimilarityWorkflow(
        scenario=scenario,
        execute_action=lambda action: _execute_scene_action(
            action,
            manager=manager,
            joystick=joystick,
        ),
        project_state=lambda: renderer.state,
        render=lambda: _render_scene_renderer(renderer, window, device.orientation),
        cleanup=lambda: _cleanup_renderer(renderer, manager),
        advance_frame=lambda delta_ms: _advance_frame(manager, delta_ms),
        transition_progress=lambda: None,
    )


def _execute_navigation_action(
    runtime: PeripheralRuntime,
    action: StateSimilarityAction,
) -> None:
    config = _mapping(action.config, label=f"{action.type}.config")
    if action.type == "keyboard":
        pressed = _sequence(config["pressed"], label="keyboard.pressed")
        snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(
                _KEY_CODES[_string(key, label="keyboard.pressed[]")]
                for key in pressed
            ),
            timestamp_ms=_number(
                config["timestamp_ms"],
                label="keyboard.timestamp_ms",
            ),
        )
        runtime.process_navigation_input(snapshot, ())
        return
    if action.type == "gamepad":
        dpad = _sequence(config["dpad"], label="gamepad.dpad")
        if len(dpad) != 2:
            raise ValueError("gamepad.dpad must contain x and y")
        held_buttons = _sequence(
            config["held_buttons"],
            label="gamepad.held_buttons",
        )
        event = GamepadSnapshotEvent(
            joystick_id=_integer(config["joystick_id"], label="gamepad.joystick_id"),
            snapshot=GamepadSnapshot(
                connected=True,
                identifier=_string(config["identifier"], label="gamepad.identifier"),
                buttons={
                    _GAMEPAD_BUTTONS[
                        _string(button, label="gamepad.held_buttons[]")
                    ]: True
                    for button in held_buttons
                },
                dpad=GamepadDpadValue(
                    x=_integer(dpad[0], label="gamepad.dpad[0]"),
                    y=_integer(dpad[1], label="gamepad.dpad[1]"),
                ),
            ),
        )
        runtime.process_navigation_input(_EMPTY_KEYBOARD, (event,))
        return
    raise ValueError(f"Unsupported navigation action {action.type!r}")


def _execute_scene_action(
    action: StateSimilarityAction,
    *,
    manager: PeripheralManager,
    joystick: _VirtualJoystick,
) -> None:
    config = _mapping(action.config, label=f"{action.type}.config")
    if action.type == "gamepad":
        axes = {
            _SWITCH_PRO_AXES[name]: _number(value, label=f"gamepad.axes.{name}")
            for name, value in _mapping(
                config["axes"],
                label="gamepad.axes",
            ).items()
        }
        buttons = {
            _SWITCH_PRO_BUTTONS[name]: _boolean(
                value,
                label=f"gamepad.buttons.{name}",
            )
            for name, value in _mapping(
                config["buttons"],
                label="gamepad.buttons",
            ).items()
        }
        joystick.set_input(axes=axes, buttons=buttons)
        manager.input_io.gamepad.poll()
        return
    if action.type == "sensor":
        acceleration = _mapping(
            config["acceleration"],
            label="sensor.acceleration",
        )
        _set_external_acceleration(
            manager,
            x=_number(acceleration["x"], label="sensor.acceleration.x"),
            y=_number(acceleration["y"], label="sensor.acceleration.y"),
            z=_number(acceleration["z"], label="sensor.acceleration.z"),
        )
        return
    if action.type == "tick":
        delta_ms = _number(config["delta_ms"], label="tick.delta_ms")
        count = _integer(config.get("count", 1), label="tick.count")
        if count <= 0:
            raise ValueError("tick.count must be positive")
        for _ in range(count):
            _advance_frame(manager, delta_ms)
        return
    raise ValueError(f"Unsupported scene-controller action {action.type!r}")


def _game_modes_transition(
    game_modes: GameModes,
) -> StateSimilarityTransition | None:
    transition = game_modes.state.sliding_transition
    if transition is None:
        return None
    if not transition.initialized:
        return StateSimilarityTransition(fraction=0.0, sliding=True)
    return StateSimilarityTransition(
        fraction=transition.state.fraction_offset,
        sliding=transition.state.sliding,
    )


def _advance_frame(manager: PeripheralManager, delta_ms: float) -> None:
    manager.input_io.frame_ticks.advance(_FrameClock(delta_ms))


def _render_navigation(
    renderers: Sequence[StatefulBaseRenderer],
    peripheral_manager: PeripheralManager,
    window: DisplayContext,
    device: Device,
) -> pygame.Surface:
    surface = ComposedRenderer.render_batch(
        renderers,
        window=window,
        peripheral_manager=peripheral_manager,
        orientation=device.orientation,
    )
    if surface is None:
        raise RuntimeError("State-similarity workflow produced no render surface")
    return surface


def _render_scene_renderer(
    renderer: Tixyland | WaterCube,
    window: DisplayContext,
    orientation: Orientation,
) -> pygame.Surface:
    if window.screen is None:
        raise RuntimeError("State-similarity workflow requires a display surface")
    window.screen.fill((0, 0, 0))
    renderer.real_process(window, orientation)
    return window.screen


def _build_device(config: Mapping[str, object]) -> Device:
    orientation_config = _mapping(
        config["orientation"],
        label="config.device.orientation",
    )
    orientation_type = _string(
        orientation_config["type"],
        label="config.device.orientation.type",
    )
    if orientation_type == "rectangle":
        orientation: Orientation = Rectangle.with_layout(
            columns=_integer(
                orientation_config["columns"],
                label="config.device.orientation.columns",
            ),
            rows=_integer(
                orientation_config["rows"],
                label="config.device.orientation.rows",
            ),
        )
    elif orientation_type == "cube_sides":
        orientation = Cube.sides()
    else:
        raise ValueError(f"Unsupported scenario orientation {orientation_type!r}")

    width = _integer(config["width"], label="config.device.width")
    height = _integer(config["height"], label="config.device.height")
    device_type = _string(config["type"], label="config.device.type")
    if device_type == "local_screen":
        return LocalScreen(width=width, height=height, orientation=orientation)
    if device_type == "fixed":
        return _FixedDevice(
            orientation=orientation,
            width=width,
            height=height,
        )
    raise ValueError(f"Unsupported scenario device {device_type!r}")


def _build_scene_renderer(
    config: Mapping[str, object],
    *,
    device: Device,
    manager: PeripheralManager,
) -> Tixyland | WaterCube:
    renderer_type = _string(config["renderer"], label="config.renderer")
    if renderer_type == "tixyland":
        pattern = _string(config["pattern"], label="config.pattern")
        if pattern != "sin_time_x_half_minus_y_quarter":
            raise ValueError(f"Unsupported Tixyland scenario pattern {pattern!r}")
        return Tixyland(
            builder=TixylandStateProvider(manager),
            fn=_tixyland_pattern,
        )
    if renderer_type == "water_cube":
        return WaterCube(builder=WaterCubeStateProvider(device=device))
    raise ValueError(f"Unsupported scenario renderer {renderer_type!r}")


def _navigation_device(config: Mapping[str, object]) -> Device:
    device_config = config.get("device")
    if device_config is None:
        return _default_navigation_device()
    return _build_device(_mapping(device_config, label="config.device"))


def _build_navigation_renderers(
    config: Mapping[str, object],
    *,
    legacy_rgb_key: str,
    label: str,
) -> list[StatefulBaseRenderer]:
    renderers_config = config.get("renderers")
    if renderers_config is None:
        return [
            RenderColor(
                _color(
                    config[legacy_rgb_key],
                    label=f"{label}.{legacy_rgb_key}",
                )
            )
        ]
    return [
        _build_navigation_renderer(
            _mapping(value, label=f"{label}.renderers[{index}]"),
            label=f"{label}.renderers[{index}]",
        )
        for index, value in enumerate(
            _sequence(renderers_config, label=f"{label}.renderers")
        )
    ]


def _compose_navigation_scene(
    renderers: Sequence[StatefulBaseRenderer],
) -> StatefulBaseRenderer:
    if not renderers:
        raise ValueError("Navigation scene must contain at least one renderer")
    if len(renderers) == 1:
        return renderers[0]
    scene = ComposedRenderer()
    scene.add_renderer(*renderers)
    return scene


def _build_navigation_renderer(
    config: Mapping[str, object],
    *,
    label: str,
) -> StatefulBaseRenderer:
    renderer_type = _string(config["type"], label=f"{label}.type")
    if renderer_type == "color":
        return RenderColor(_color(config["rgb"], label=f"{label}.rgb"))
    if renderer_type == "border":
        return Border(
            width=_integer(config["width"], label=f"{label}.width"),
            color=_color(config["rgb"], label=f"{label}.rgb"),
        )
    raise ValueError(f"Unsupported navigation renderer {renderer_type!r}")


def _tixyland_pattern(
    time: float,
    _index: np.ndarray,
    y: np.ndarray,
    x: np.ndarray,
) -> np.ndarray:
    return np.sin(time + x * 0.5 - y * 0.25)


def _manager_with_gamepad(
    name: str,
) -> tuple[PeripheralManager, _VirtualJoystick]:
    manager = PeripheralManager()
    joystick = _VirtualJoystick(name)
    manager.register(Gamepad(joystick_id=0, joystick=joystick))
    return manager, joystick


def _set_external_acceleration(
    manager: PeripheralManager,
    *,
    x: float,
    y: float,
    z: float,
) -> None:
    sensors = manager.input_io.external_sensors
    sensors.set_value("workflow-accelerometer:x", x)
    sensors.set_value("workflow-accelerometer:y", y)
    sensors.set_value("workflow-accelerometer:z", z)
    manager.input_io.accelerometer.node().on_next(Acceleration(x=x, y=y, z=z))


def _window(device: Device) -> DisplayContext:
    return DisplayContext(
        device=device,
        screen=pygame.Surface(device.full_display_size()),
        clock=pygame.time.Clock(),
    )


def _default_navigation_device() -> Device:
    return _FixedDevice(
        orientation=Cube.sides(),
        width=64,
        height=64,
    )


def _cleanup_renderer(
    renderer: StatefulBaseRenderer,
    peripheral_manager: PeripheralManager,
) -> None:
    renderer.reset()
    peripheral_manager.stop()


def _color(value: object, *, label: str) -> Color:
    rgb = _sequence(value, label=label)
    if len(rgb) != 3:
        raise ValueError(f"{label} must contain three channels")
    return Color(
        _integer(rgb[0], label=f"{label}[0]"),
        _integer(rgb[1], label=f"{label}[1]"),
        _integer(rgb[2], label=f"{label}[2]"),
    )


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} must use string keys")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    return value


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} must be a number")
    return float(value)


def _boolean(value: object, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be a boolean")
    return value
