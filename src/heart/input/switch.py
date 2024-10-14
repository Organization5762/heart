import json

import serial

from heart.input import RunnableIO, Subscriber
from heart.utilities.env import Configuration

ACTIVE_SWITCH = None


class BaseSwitch(RunnableIO):
    def __init__(self) -> None:
        self.rotational_value = 0
        self.button_value = 0
        self.rotation_value_at_last_button_press = self.rotational_value

    def run(self) -> None:
        return

    def get_rotation_since_last_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_button_press

    def get_rotational_value(self) -> int:
        return self.rotational_value

    def get_button_value(self) -> int:
        return self.button_value

    def _update_due_to_data(self, data: dict) -> None:
        event_type = data["event_type"]
        data_value = data["data"]

        if event_type == "rotation":
            self.rotational_value = int(data_value)

        if event_type == "button":
            self.button_value += int(data_value)
            # Button was pressed, update last_rotational_value
            self.rotation_value_at_last_button_press = self.rotational_value


class FakeSwitch(BaseSwitch):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        return


class Switch(BaseSwitch):
    def __init__(self, *args, **kwargs) -> None:
        self.port = "/dev/ttyACM0"
        self.baudrate = 115200
        super().__init__(*args, **kwargs)

    def _connect_to_ser(self):
        return serial.Serial(self.port, self.baudrate)

    def run(self):
        # If it crashes, try to re-connect
        while True:
            try:
                ser = self._connect_to_ser()
                try:
                    while True:
                        if ser.in_waiting > 0:
                            bus_data = ser.readline().decode("utf-8").rstrip()
                            data = json.loads(bus_data)
                            self._update_due_to_data(data)
                except KeyboardInterrupt:
                    print("Program terminated")
                except Exception:
                    pass
                finally:
                    ser.close()
            except Exception:
                pass


class SwitchSubscriber(Subscriber[BaseSwitch]):
    def __init__(self, switch: BaseSwitch) -> None:
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is not None:
            raise Exception("Switch already initialized")

        self.switch = switch

    @classmethod
    def get(cls):
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is None:
            if Configuration.is_pi():
                s = Switch()
            else:
                s = FakeSwitch()

            switch = SwitchSubscriber(switch=s)
            ACTIVE_SWITCH = switch
        return ACTIVE_SWITCH

    def run(self):
        self.switch.run()

    def get_switch(self):
        return self.switch

    def get_rotation_since_last_button_press(self) -> int:
        return self.get_switch().get_rotation_since_last_button_press()

    def get_rotational_value(self) -> int:
        return self.get_switch().get_rotational_value()

    def get_button_value(self) -> int:
        return self.get_switch().get_button_value()
