from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class DpadType(Enum):
    HAT = 0
    BUTTONS = 1


class SwitchLikeMapping(ABC):
    def get_dpad_type(self) -> DpadType:
        return self.DPAD_TYPE

    @property
    @abstractmethod
    def DPAD_TYPE(self) -> DpadType:
        pass

    @property
    def DPAD_HAT(self) -> Optional[int]:
        return None

    # d-pad buttons
    @property
    def DPAD_UP(self) -> Optional[int]:
        return None

    @property
    def DPAD_DOWN(self) -> Optional[int]:
        return None

    @property
    def DPAD_LEFT(self) -> Optional[int]:
        return None

    @property
    def DPAD_RIGHT(self) -> Optional[int]:
        return None

    # face buttons
    @property
    @abstractmethod
    def BUTTON_A(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_B(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_X(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_Y(self) -> int:
        pass

    # option buttons
    @property
    @abstractmethod
    def BUTTON_PLUS(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_MINUS(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_HOME(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_CAPTURE(self) -> int:
        pass

    # trigger buttons
    @property
    @abstractmethod
    def BUTTON_ZL(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_ZR(self) -> int:
        pass

    # "analogue" triggers
    @property
    @abstractmethod
    def AXIS_L(self) -> int:
        pass

    @property
    @abstractmethod
    def AXIS_R(self) -> int:
        pass

    # analogue joystick axes
    @property
    @abstractmethod
    def AXIS_LEFT_X(self) -> int:
        pass

    @property
    @abstractmethod
    def AXIS_LEFT_Y(self) -> int:
        pass

    @property
    @abstractmethod
    def AXIS_RIGHT_X(self) -> int:
        pass

    @property
    @abstractmethod
    def AXIS_RIGHT_Y(self) -> int:
        pass

    # joystick buttons
    @property
    @abstractmethod
    def BUTTON_L3(self) -> int:
        pass

    @property
    @abstractmethod
    def BUTTON_R3(self) -> int:
        pass


class BitDoLite2(SwitchLikeMapping):
    DPAD_TYPE = DpadType.HAT
    DPAD_HAT = 0

    # face buttons
    BUTTON_A = 0
    BUTTON_B = 1
    BUTTON_X = 2
    BUTTON_Y = 3

    # options buttons
    BUTTON_PLUS = 10
    BUTTON_MINUS = 8
    BUTTON_HOME = 9

    # button seems to not register on bitdo lite 2
    BUTTON_CAPTURE = -1

    # stick buttons
    BUTTON_L3 = 6
    BUTTON_R3 = 7

    # left stick axis
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1

    # right stick axis
    AXIS_RIGHT_X = 3
    AXIS_RIGHT_Y = 4

    # trigger axis
    AXIS_L = 2
    AXIS_R = 5

    # trigger buttons
    BUTTON_ZL = 4
    BUTTON_ZR = 5


class BitDoLite2BluetoothPi4(SwitchLikeMapping):
    DPAD_TYPE = DpadType.HAT
    DPAD_HAT = 0

    # face buttons
    BUTTON_A = 0
    BUTTON_B = 1
    BUTTON_X = 3
    BUTTON_Y = 4

    # options buttons
    BUTTON_PLUS = 11
    BUTTON_MINUS = 10
    BUTTON_HOME = 12

    # button seems to not register on bitdo lite 2
    BUTTON_CAPTURE = -1

    # stick buttons
    BUTTON_L3 = 13
    BUTTON_R3 = 14

    # left stick axis
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1

    # right stick axis
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3

    # trigger axis
    AXIS_L = 5
    AXIS_R = 4

    # trigger buttons
    BUTTON_ZL = 6
    BUTTON_ZR = 7


class BitDoLite2Bluetooth(SwitchLikeMapping):
    DPAD_TYPE = DpadType.HAT
    DPAD_HAT = 0

    # face buttons
    BUTTON_A = 0
    BUTTON_B = 1
    BUTTON_X = 3
    BUTTON_Y = 4

    # options buttons
    BUTTON_PLUS = 11
    BUTTON_MINUS = 10
    BUTTON_HOME = 12

    # button seems to not register on bitdo lite 2
    BUTTON_CAPTURE = -1

    # stick buttons
    BUTTON_L3 = 13
    BUTTON_R3 = 14

    # left stick axis
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1

    # right stick axis
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3

    # trigger axis
    AXIS_L = 5
    AXIS_R = 4

    # trigger buttons
    BUTTON_ZL = 6
    BUTTON_ZR = 7


class SwitchProMapping(SwitchLikeMapping):
    DPAD_TYPE = DpadType.BUTTONS

    DPAD_HAT = -1

    # d-pad buttons
    DPAD_UP = 11
    DPAD_DOWN = 12
    DPAD_LEFT = 13
    DPAD_RIGHT = 14

    # face buttons
    BUTTON_A = 0
    BUTTON_B = 1
    BUTTON_X = 2
    BUTTON_Y = 3

    # option buttons
    BUTTON_PLUS = 6
    BUTTON_MINUS = 4
    BUTTON_HOME = 5
    BUTTON_CAPTURE = 15

    # trigger buttons
    BUTTON_ZL = 9
    BUTTON_ZR = 10

    # "analogue" triggers (they're not actually analogue ¯\_(ツ)_/¯)
    AXIS_L = 4
    AXIS_R = 5

    # analogue joystick axes
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3

    # joystick buttons
    BUTTON_L3 = 7
    BUTTON_R3 = 8
