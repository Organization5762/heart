from heart.input.env import Environment

class BaseHeartRate:
    def __init__(self) -> None:
        pass
    
    def run(self) -> None:
        return

class FakeSwitch(BaseHeartRate):
    def __init__(self) -> None:
        pass
        
    def run(self) -> None:
        return
        
class Switch(BaseHeartRate):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
    def run(self):
        try:
            while True:
                if self.ser.in_waiting > 0:
                    # TODO (lampe): Handle button state too
                    # Will likely switch this over to a JSON format + update the driver on the encoder
                    data = self.ser.readline().decode('utf-8').rstrip()
                    self.rotational_value = data
        except KeyboardInterrupt:
            print("Program terminated")
        finally:
            self.get().ser.close()
# TODO: Move this out into `input/heart_rate.py` or so similar to switch.py
def detect_heart_rate(screens):
    node = Node()
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    device = HeartRate(node, device_id=0)

    def on_found():
        print(f"Device {device} found and receiving")

    def on_device_data(page: int, page_name: str, data):
        if isinstance(data, HeartRateData) and page == 128:
            print(f"Heart rate update {data.beat_count} beats from {page} {page_name}")
            screens[0].add_data(data)

    device.on_found = on_found
    device.on_device_data = on_device_data

    try:
        print(f"Starting {device}, press Ctrl-C to finish")
        node.start()
    except KeyboardInterrupt:
        print("Closing ANT+ device...")
    finally:
        device.close_channel()
        node.stop()
        
class HeartRateSubscriber:
    def __init__(self, switch: BaseSwitch) -> None:
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is not None:
            raise Exception("Switch already initialized")
        
        self.switch = switch
                    
    @classmethod
    def get(cls):
        global ACTIVE_SWITCH
        if ACTIVE_SWITCH is None:
            if Environment.is_pi():
                switch = Switch()
            else:
                switch = FakeSwitch()
                
            switch = SwitchSubscriber(switch=switch)
            ACTIVE_SWITCH = switch
        return ACTIVE_SWITCH

    def run(self):
        self.switch.run()
        
    def get_switch(self):
        return self.switch
    
    def get_rotational_value(self) -> int:
        return self.get_switch().get_rotational_value()
    
    def get_button_value(self) -> int:
        return self.get_switch().get_button_value()
    