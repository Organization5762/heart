import reactivex
from reactivex import operators as ops

from heart.peripheral.core import InputDescriptor, PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.switch import FakeSwitch, SwitchState


class MainSwitchProvider(ObservableProvider[SwitchState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def inputs(self) -> tuple[InputDescriptor, ...]:
        main_switches = [
            peripheral.observe
            for peripheral in self._pm.peripherals
            if isinstance(peripheral, FakeSwitch)
        ]
        switch_stream = (
            reactivex.merge(*main_switches)
            if main_switches
            else reactivex.empty()
        )
        return (
            InputDescriptor(
                name="fake_switch.observe",
                stream=switch_stream,
                payload_type=SwitchState,
                description="Observable stream emitted by FakeSwitch peripherals.",
            ),
        )

    def observable(self) -> reactivex.Observable[SwitchState]:
        main_switches = [
            peripheral.observe
            for peripheral in self._pm.peripherals
            if isinstance(peripheral, FakeSwitch)
        ]
        return reactivex.merge(*main_switches).pipe(
            ops.map(PeripheralMessageEnvelope[SwitchState].unwrap_peripheral)
        )
