from heart.input.env import Environment
import serial

ACTIVE_SWITCH = None

class BaseSwitch:
    def __init__(self) -> None:
        self.rotational_value = 0
        self.button_value = 0
        
    def run(self) -> None:
        return
    
    def get_rotational_value(self) -> int:
        return self.rotational_value
    
    def get_button_value(self) -> int:
        return self.button_value

class FakeSwitch(BaseSwitch):
    def __init__(self) -> None:
        self.rotational_value = 0
        self.button_value = 0
        
    def run(self) -> None:
        return
        
class Switch(BaseSwitch):
    def __init__(self, *args, **kwargs) -> None:
        self.ser = serial.Serial('/dev/ttyACM0', 115200)
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

class SwitchSubscriber:
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
    
    def get_rotational_value(self) -> int:
        return self.get_switch().get_rotational_value()
    
    def get_button_value(self) -> int:
        return self.get_switch().get_button_value()
    
