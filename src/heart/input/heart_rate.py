import random
import threading
import time

from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.common import DeviceType
from openant.devices.heart_rate import HeartRateData
from openant.devices.scanner import Scanner
from openant.devices.utilities import auto_create_device
from openant.easy.node import Node

from heart.input import Subscriber
from heart.utilities.env import Configuration


class BaseHeartRate:
    def __init__(self) -> None:
        pass

    def run(self) -> None:
        pass


class FakeHeartRateSensor(BaseHeartRate):
    def __init__(self) -> None:
        self.current_state = {
            65535: 80,
            65535: 75,
            65535: 60,
            65535: 92,
        }

    def compute_bpms(self):
        for k, v in self.current_state.items():
            self.current_state[k] = int(v + random.randint(-5, 5))
        return self.current_state

    def run(self) -> None:
        return


def compute_bpm(data: list[HeartRateData]):
    first_element = data[0]
    last_element = data[-1]

    time_it_took = last_element.beat_time - first_element.beat_time
    beats = last_element.beat_count - first_element.beat_count

    expected = last_element.heart_rate

    if time_it_took == 0 or beats == 0:
        return expected, expected

    bpm = (60 / time_it_took) * beats
    return bpm, expected


def windowed_mean(data, window_size: int):
    computed_bpm = []
    for idx in range(len(data) - window_size - 1):
        this_data = data[idx : idx + window_size]

        # Let's just do the ASAP distance, so time between two betweens normalized to a minute

        all_values = [
            compute_bpm(this_data[i : i + 2])[0] for i in range(window_size - 2)
        ]

        bpm = sum(all_values) / len(all_values)

        computed_bpm.append(bpm)

    if len(computed_bpm) == 0:
        return 0

    return sum(computed_bpm) / len(computed_bpm)


class HeartRateSensor(BaseHeartRate):
    def __init__(self, *args, **kwargs) -> None:
        self.heart_rates = {}
        self.window_size = 4
        super().__init__(*args, **kwargs)

    def compute_bpms(self):
        return {
            (k, windowed_mean(v, self.window_size)) for k, v in self.heart_rates.items()
        }

    def run(self):
        # TODO (lampe): We'll need to fix this for multiple devices as it just goes for the FIRST,
        # which only works for one device
        device_id = 0
        device_type = 0

        node = Node()
        node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

        # list of auto created devices
        devices = []

        # the scanner
        scanner = Scanner(node, device_id=device_id, device_type=device_type)

        # local function to call when device updates common data
        def on_update(device_tuple, common):
            device_id = device_tuple[0]
            print(f"Device #{device_id} commond data update: {common}")

        def on_device_data(page: int, page_name: str, data):
            if isinstance(data, HeartRateData):
                key = data.serial_number
                if key not in self.heart_rates:
                    self.heart_rates[key] = []

                self.heart_rates[key].append(data)
                if len(self.heart_rates) > self.window_size:
                    self.heart_rates = self.heart_rates[1:]

        # local function to call when a device is found - also does the auto-create if enabled
        def on_found(device_tuple):
            device_id, device_type, device_trans = device_tuple
            print(
                f"Found new device #{device_id} {DeviceType(device_type)}; device_type: {device_type}, transmission_type: {device_trans}"
            )

            if len(devices) < 16:
                try:
                    dev = auto_create_device(node, device_id, device_type, device_trans)
                    # closure callback of on_device_data with device
                    dev.on_device_data = lambda _, page_name, data: on_device_data(
                        dev, page_name, data
                    )
                    devices.append(dev)
                except Exception as e:
                    print(f"Could not auto create device: {e}")

        # add callback functions to scanner
        scanner.on_found = on_found
        scanner.on_update = on_update

        # start scanner, exit on keyboard and clean up USB device on exit
        # try:
        print(
            f"Starting scanner for #{device_id}, type {device_type}, press Ctrl-C to finish"
        )
        while True:
            try:
                # This should block, but the While true allows it to possibly recover
                node.start()
            finally:
                scanner.close_channel()

                for dev in devices:
                    dev.close_channel()

                node.stop()


ACTIVE_SWITCH: BaseHeartRate = None


class HeartRateSubscriber(Subscriber[BaseHeartRate]):
    def __init__(self, switch: BaseHeartRate) -> None:
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is not None:
            raise Exception("Switch already initialized")

        self.switch = switch

    @classmethod
    def get(cls):
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is None:
            if Configuration.is_pi():
                switch = HeartRateSensor()
            else:
                switch = FakeHeartRateSensor()

            switch = HeartRateSubscriber(switch=switch)
            ACTIVE_SWITCH = switch
        return ACTIVE_SWITCH

    def run(self):
        self.switch.run()

    def get_heart_rate(self):
        return self.switch.compute_bpms()


if __name__ == "__main__":
    t = threading.Thread(target=HeartRateSubscriber.get().run)
    t.start()

    while True:
        print(HeartRateSubscriber.get().get_heart_rate())
        time.sleep(0.5)
