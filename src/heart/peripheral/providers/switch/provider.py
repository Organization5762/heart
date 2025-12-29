import reactivex
from reactivex import operators as ops

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.switch import FakeSwitch, SwitchState
from heart.utilities.reactivex_threads import pipe_in_background


class MainSwitchProvider(ObservableProvider[SwitchState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def _switch_stream(self) -> reactivex.Observable[SwitchState]:
        main_switches = [
            peripheral.observe
            for peripheral in self._pm.peripherals
            if isinstance(peripheral, FakeSwitch)
        ]
        if not main_switches:
            return reactivex.empty()
        return pipe_in_background(
            reactivex.merge(*main_switches),
            ops.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )

    def observable(self) -> reactivex.Observable[SwitchState]:
        return self._switch_stream()
