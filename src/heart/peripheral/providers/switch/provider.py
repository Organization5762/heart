import reactivex
from reactivex import operators as ops

from heart.peripheral.core import InputDescriptor, PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.switch import FakeSwitch, SwitchState


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
        return reactivex.merge(*main_switches).pipe(
            ops.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )

    def inputs(self) -> tuple[InputDescriptor, ...]:
        return (
            InputDescriptor(
                name="fake_switch.observe.state",
                stream=self._switch_stream(),
                payload_type=SwitchState,
                description="Observable stream of SwitchState updates from FakeSwitch.",
            ),
        )

    def observable(self) -> reactivex.Observable[SwitchState]:
        return self._switch_stream()
