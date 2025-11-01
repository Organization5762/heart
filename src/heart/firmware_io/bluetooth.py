
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService


ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

END_OF_MESSAGE_DELIMETER = "\n"
ENCODING = "utf-8"


# TODO: AAddDd a bulk write command
def send(messages: list[str]):
    if not ble.advertising:
        ble.start_advertising(advertisement)

    if ble.connected:
        # We're connected, make sure the buffer is drained as the first priority
        for message in messages:
            uart.write(message.encode(ENCODING))
            uart.write(END_OF_MESSAGE_DELIMETER.encode(ENCODING))
