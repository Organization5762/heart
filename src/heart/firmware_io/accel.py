import json

from adafruit_lis2mdl import LIS2MDL
from adafruit_lsm6ds import Rate
from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
from adafruit_lsm303_accel import LSM303_Accel

from heart.firmware_io import constants


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
        "data": {
            "value": data,
        },
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
        },
    )


class SensorReader:
    """Tracks last values and determines when updates are significant."""

    def __init__(self, sensors, min_change: float = 0.1) -> None:
        self.sensors = sensors
        self.min_change = min_change

        self._last_accel: tuple | None = None
        self._last_gyro: tuple | None = None

    def read(self):
        for sensor in self.sensors:
            """Yield JSON strings for each channel that crossed ``min_change``."""
            if hasattr(sensor, "acceleration"):
                accel = sensor.acceleration  # m/s²
                if self._changed_enough(accel, self._last_accel, self.min_change):
                    self._last_accel = accel
                    yield form_tuple_payload(constants.ACCELERATION, accel)

            if hasattr(sensor, "gyro"):
                gyro = sensor.gyro
                if self._changed_enough(gyro, self._last_gyro, self.min_change):
                    self._last_gyro = gyro
                    yield form_tuple_payload(constants.GYROSCOPE, gyro)

    def _changed_enough(self, new: tuple, old: tuple | None, min_change: float) -> bool:
        """Return *True* if any axis differs by more than *min_change*."""
        if old is None:
            return True
        return any(abs(n - o) > min_change for n, o in zip(new, old))

    @classmethod
    def connect(cls, i2c, min_change: float = 0.1):
        sensors = cls.connect_to_sensors(i2c=i2c)
        return cls(sensors=sensors, min_change=min_change)

    @classmethod
    def connect_to_sensors(cls, i2c):
        """Establishes a connection to the ISM330DHCX sensor using I2C communication.

        This function initializes the I2C bus on the specified board pins and
        returns an instance of the ISM330DHCX sensor.

        Technical References:
        - `board.RX`: The receive pin on the board used for I2C communication.
        - `board.TX`: The transmit pin on the board used for I2C communication.
        - `busio.I2C`: The I2C bus interface for communication with the sensor.
        - `ISM330DHCX`: The 6-DoF IMU sensor from Adafruit.

        Returns:
            LSM303_Accel
            LIS2MDL
            ISM330DHCX: An instance of the ISM330DHCX sensor.

        """
        sensor_fn = [
            LSM303_Accel,
            LIS2MDL,
            ISM330DHCX,
        ]
        sensors = []
        for sensor_fn in sensor_fn:
            try:
                sensors.append(sensor_fn(i2c))
            except Exception:
                pass
        return sensors

    def get_sample_rate(self, sensor) -> float:
        """
        Max interval defined by device rate
        Reference: https://github.com/adafruit/Adafruit_CircuitPython_LSM6DS/blob/main/adafruit_lsm6ds/__init__.py#L108-L123

        I put this up here because it is quite likely we'll just want to
        For now, assume gyro and acceleration will be the same
        """
        if hasattr(sensor, "accelerometer_data_rate"):
            check_interval = sensor.accelerometer_data_rate
        else:
            check_interval = Rate.RATE_104_HZ
        return Rate.string[check_interval]
