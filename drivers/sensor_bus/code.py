"""Stream sensor bus readings over serial and document REPL debugging steps.

REPL reproduction:
    1. Connect to the board REPL and import this module.
    2. Run ``main()`` to stream JSON payloads over serial.
    3. Toggle ``DEBUG = True`` and call ``connect_to_sensors(board.STEMMA_I2C())``
       to surface initialization failures without running the full game runtime.
"""

import json
import time

import board
import busio
from adafruit_lis2mdl import LIS2MDL
from adafruit_lsm6ds import Rate
from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
from adafruit_lsm303_accel import LSM303_Accel

from heart_firmware_io import constants, device_id, identity

WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS: float = 1.0
DEFAULT_WAIT_BETWEEN_PAYLOADS_SECONDS: float = 0.1
DEFAULT_MIN_CHANGE_THRESHOLD: float = 0.1
DEBUG = False
DEVICE_NAME = "sensor-bus"
RUN_MODULE_NAMES = {"__main__", "code"}
LSM303_ACCEL_ADDRESSES = (0x19,)
LIS2MDL_ADDRESSES = (0x1E,)
ISM330DHCX_ADDRESSES = (0x6A, 0x6B)


def create_i2c_bus():
    """Return the configured sensor I2C bus for STEMMA/Qwiic wiring."""
    if hasattr(board, "STEMMA_I2C"):
        try:
            return board.STEMMA_I2C()
        except Exception as exc:  # noqa: BLE001
            _debug("Failed to initialize board.STEMMA_I2C(): %s" % exc)
    return busio.I2C(board.RX, board.TX)


def _debug(message: str) -> None:
    if DEBUG:
        print(message)


def _write_serial_bus(message: str) -> None:
    """Emit the event payload over the serial bus."""

    print(message, end="")


IDENTITY = identity.Identity(
    device_name=DEVICE_NAME,
    firmware_commit=identity.default_firmware_commit(),
    device_id=device_id.persistent_device_id(),
)


def respond_to_identify_query(*, stdin=None, print_fn=print) -> bool:
    """Process any pending Identify query."""

    return identity.poll_and_respond(IDENTITY, stdin=stdin, print_fn=print_fn)


def get_sample_rate(sensor) -> float:
    # Max interval defined by device rate
    # Reference: https://github.com/adafruit/Adafruit_CircuitPython_LSM6DS/blob/main/adafruit_lsm6ds/__init__.py#L108-L123
    #
    # I put this up here because it is quite likely we'll just want to
    # For now, assume gyro and acceleration will be the same
    if hasattr(sensor, "accelerometer_data_rate"):
        check_interval = sensor.accelerometer_data_rate
    else:
        check_interval = Rate.RATE_104_HZ
    return Rate.string[check_interval]


def _form_payload(name: str, data) -> str:
    """Forms a JSON payload string from a dictionary of data.

    Args:
        name (str): The event type name.
        data (dict[str, float]): A dictionary containing data values.

    Returns:
        str: A JSON string representing the payload.

    """
    payload = {"event_type": name, "data": data}
    return f"{json.dumps(payload)}\n"


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


def connect_to_sensors(i2c):
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
    scanned_addresses = _scan_i2c_addresses(i2c)
    sensor_factories = [
        (LSM303_Accel, LSM303_ACCEL_ADDRESSES),
        (LIS2MDL, LIS2MDL_ADDRESSES),
        (ISM330DHCX, ISM330DHCX_ADDRESSES),
    ]
    sensors = []
    for sensor_factory, expected_addresses in sensor_factories:
        if scanned_addresses is not None and not _has_any_address(
            scanned_addresses, expected_addresses
        ):
            _debug(
                "Skipping sensor %s; addresses %s not present"
                % (sensor_factory.__name__, expected_addresses)
            )
            continue
        try:
            sensors.append(sensor_factory(i2c))
        except Exception as exc:  # noqa: BLE001
            _debug(
                "Failed to initialize sensor %s: %s" % (sensor_factory.__name__, exc)
            )
    return sensors


def _scan_i2c_addresses(i2c):
    if not hasattr(i2c, "try_lock") or not hasattr(i2c, "scan"):
        return None
    try:
        while not i2c.try_lock():
            time.sleep(0.01)
        try:
            return tuple(i2c.scan())
        finally:
            i2c.unlock()
    except Exception as exc:  # noqa: BLE001
        _debug("Failed to scan I2C bus: %s" % exc)
        return None


def _has_any_address(scanned_addresses, expected_addresses) -> bool:
    return any(address in scanned_addresses for address in expected_addresses)


class SensorReader:
    """Tracks last values and determines when updates are significant."""

    def __init__(
        self, sensors, min_change: float = DEFAULT_MIN_CHANGE_THRESHOLD
    ) -> None:
        self.sensors = sensors
        self.min_change = min_change

        self._last_accel: tuple | None = None
        self._last_gyro: tuple | None = None
        self._last_mag: tuple | None = None

    def read(self):
        """Yield JSON strings for each channel that crossed ``min_change``."""
        for sensor in self.sensors:
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

            if hasattr(sensor, "magnetic"):
                mag = sensor.magnetic
                if self._changed_enough(mag, self._last_mag, self.min_change):
                    self._last_mag = mag
                    yield form_tuple_payload(constants.MAGNETIC, mag)

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
    i2c = create_i2c_bus()
    sensors = connect_to_sensors(i2c=i2c)

    # This assumes two things:
    # 1. We care about the more precise data possibly (e.g. power by damned)
    # 2. That actually checking the sensor takes roughly 0 time
    sample_rates = [(1000 / get_sample_rate(sensor)) / 1000 for sensor in sensors]
    if len(sample_rates) == 0:
        wait_between_payloads_seconds = DEFAULT_WAIT_BETWEEN_PAYLOADS_SECONDS
    else:
        wait_between_payloads_seconds = min(sample_rates)

    sr = SensorReader(sensors=sensors, min_change=DEFAULT_MIN_CHANGE_THRESHOLD)

    while True:
        try:
            respond_to_identify_query()
            if sensors is None:
                sensors = connect_to_sensors(i2c=i2c)

            for sensor_data_payload in sr.read():
                _write_serial_bus(sensor_data_payload)

            # This also has a `temperature` field but I'm not sure if that's chip temperature or ambient
            time.sleep(wait_between_payloads_seconds)
        except OSError:
            sensors = None
            time.sleep(WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS)


if __name__ in RUN_MODULE_NAMES:
    main()
