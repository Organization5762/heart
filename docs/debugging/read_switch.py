import serial

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

ser = serial.Serial("/dev/ttyACM0", 115200)

try:
    while True:
        if ser.in_waiting > 0:
            # TODO (lampe): Handle button state too
            # Will likely switch this over to a JSON format + update the driver on the encoder
            data = ser.readline().decode("utf-8").rstrip()
            logger.info("%s", data)
except KeyboardInterrupt:
    logger.info("Program terminated")
finally:
    ser.close()
