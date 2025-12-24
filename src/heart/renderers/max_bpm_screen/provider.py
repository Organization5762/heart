from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.heart_rates import current_bpms
from heart.renderers.max_bpm_screen.state import AvatarBpmRendererState

AVATAR_MAPPINGS = {
    "sri": "0E906",  # PINK
    "clem": "0EA8E",  # Green
    "faye": "0ED2A",  # YELLOW
    "will": "09F90",  # BLACK
    "seb": "0EA01",  # RED
    "lampe": "0EA19",  # BLUE
    "cal": "0EB14",  # PURPLE
    "ditto": "08E5F",  # WHITE
}


class AvatarBpmStateProvider(ObservableProvider[AvatarBpmRendererState]):
    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[AvatarBpmRendererState]:
        return (
            peripheral_manager.game_tick.pipe(
                ops.map(lambda _: self._select_top_bpm()),
                ops.start_with(
                    AvatarBpmRendererState(sensor_id=None, bpm=None, avatar_name=None)
                ),
                ops.distinct_until_changed(),
                ops.share(),
            )
        )

    def _select_top_bpm(self) -> AvatarBpmRendererState:
        if not current_bpms:
            return AvatarBpmRendererState(sensor_id=None, bpm=None, avatar_name=None)

        try:
            active_bpms = [
                (addr, bpm) for addr, bpm in current_bpms.items() if bpm > 0
            ]
        except ValueError:
            return AvatarBpmRendererState(sensor_id=None, bpm=None, avatar_name=None)

        if not active_bpms:
            return AvatarBpmRendererState(sensor_id=None, bpm=None, avatar_name=None)

        sorted_bpms = sorted(active_bpms, key=lambda x: x[1], reverse=True)
        sensor_id, bpm = sorted_bpms[0]

        avatar_name = "faye"
        for name, device_id in AVATAR_MAPPINGS.items():
            if sensor_id == device_id:
                avatar_name = name
                break

        return AvatarBpmRendererState(
            sensor_id=sensor_id, bpm=bpm, avatar_name=avatar_name
        )
