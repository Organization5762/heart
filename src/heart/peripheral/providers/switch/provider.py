from manyfold import EmptyNode
from manyfold.architecture import PubSubObservable

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.peripheral.switch import FakeSwitch, SwitchState


class MainSwitchProvider(ObservableProvider[SwitchState]):
    def __init__(self, peripheral_manager: PeripheralManager):
        self._pm = peripheral_manager

    def _switch_stream(self) -> Variable[SwitchState]:
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

    def observable(self, *args: object, **kwargs: object) -> Variable[SwitchState]:
        return self._switch_stream()
