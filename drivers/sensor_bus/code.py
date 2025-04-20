from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
from adafruit_lsm6ds import Rate
import time
import board
import json
from heart.firmware_io import constants

WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS: float = 1.0

def get_sample_rate(sensor) -> float:
    # Max interval defined by device rate
    # Reference: https://github.com/adafruit/Adafruit_CircuitPython_LSM6DS/blob/main/adafruit_lsm6ds/__init__.py#L108-L123
    #
    # I put this up here because it is quite likely we'll just want to 
    # For now, assume gyro and acceleration will be the same
    check_interval = sensor.accelerometer_data_rate
    update_hz = Rate.string[check_interval]
    return update_hz


def _form_payload(name: str, data) -> str:
    """Forms a JSON payload string from a dictionary of data.

    Args:
        name (str): The event type name.
        data (dict[str, float]): A dictionary containing data values.

    Returns:
        str: A JSON string representing the payload.

    """
    payload = {
        "event_type": name,
        "data": data
    }
    return "\n" + json.dumps(payload) + "\n"


def form_tuple_payload(name: str, data: tuple) -> str:
    """Forms a JSON payload string from a tuple of data.

    Args:
        name (str): The event type name.
        data (tuple): A tuple containing three float values representing x, y, and z coordinates.

    Returns:
        str: A JSON string representing the payload.

    """
    return _form_payload(
        name,
        data={
            "x": data[0],
            "y": data[1],
            "z": data[2],
        }
    )

def connect_to_sensor(i2c):
    """Establishes a connection to the ISM330DHCX sensor using I2C communication.

    This function initializes the I2C bus on the specified board pins and
    returns an instance of the ISM330DHCX sensor.

    Technical References:
    - `board.RX`: The receive pin on the board used for I2C communication.
    - `board.TX`: The transmit pin on the board used for I2C communication.
    - `busio.I2C`: The I2C bus interface for communication with the sensor.
    - `ISM330DHCX`: The 6-DoF IMU sensor from Adafruit.

    Returns:
        ISM330DHCX: An instance of the ISM330DHCX sensor.

    """
    return ISM330DHCX(i2c)

class SensorReader:
    """Tracks last values and determines when updates are significant."""

    def __init__(self, sensor, min_change: float = 0.1) -> None:
        self.sensor = sensor
        self.min_change = min_change

        self._last_accel: tuple | None = None
        self._last_gyro: tuple | None = None

    def read(self):
        """Yield JSON strings for each channel that crossed ``min_change``."""
        accel = self.sensor.acceleration  # m/s²
        gyro = self.sensor.gyro  # rad/s

        if self._changed_enough(accel, self._last_accel, self.min_change):
            self._last_accel = accel
            yield form_tuple_payload(constants.ACCELERATION, accel)

        if self._changed_enough(gyro, self._last_gyro, self.min_change):
            self._last_gyro = gyro
            yield form_tuple_payload(constants.GYROSCOPE, gyro)

    def _changed_enough(self, new: tuple, old: tuple | None, min_change: float) -> bool:
        """Return *True* if any axis differs by more than *min_change*."""
        if old is None:
            return True
        return any(abs(n - o) > min_change for n, o in zip(new, old))

def main() -> None:
    """Main function to read sensor data and print it in JSON format.

    This function connects to the ISM330DHCX sensor and continuously reads
    acceleration and angular velocity data. The data is then formatted into
    JSON strings and printed. If a connection error occurs, it attempts to
    reconnect to the sensor after a specified wait time.

    Raises:
        OSError: If an error occurs during sensor data reading or connection.

    """
    i2c = board.STEMMA_I2C()
    sensor = connect_to_sensor(i2c=i2c)

    # This assumes two things:
    # 1. We care about the more precise data possibly (e.g. power by damned)
    # 2. That actually checking the sensor takes roughly 0 time
    wait_between_payloads_seconds = (1000 / get_sample_rate(sensor)) / 1000

    sr = SensorReader(sensor=sensor, min_change=0.1)


    while True:
        try:
            if sensor is None:
                sensor = connect_to_sensor(i2c=i2c)

            for sensor_data_payload in sr.read():
                print(sensor_data_payload)

            # This also has a `temperature` field but I'm not sure if that's chip temperature or ambient
            time.sleep(wait_between_payloads_seconds)
        except (OSError) as e:
            sensor = None
            time.sleep(WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS)
        except BaseException as e:
            raise e

main()