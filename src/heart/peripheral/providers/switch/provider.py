from manyfold import EmptyNode, Subscribable
from manyfold.architecture import PubSubObservable

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.peripheral.switch import FakeSwitch, SwitchState


class MainSwitchProvider(StateProvider[SwitchState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def _switch_stream(self) -> Subscribable[SwitchState]:
        main_switches = [
            peripheral.observe
            for peripheral in self._pm.peripherals
            if isinstance(peripheral, FakeSwitch)
        ]
        if not main_switches:
            return EmptyNode().observable()
        result = PubSubObservable.merge(*main_switches).map(
            PeripheralMessageEnvelope[SwitchState].unwrap_peripheral
        )
        return result

    def states(self, *args: object, **kwargs: object) -> Subscribable[SwitchState]:
        return self._switch_stream()
