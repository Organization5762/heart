from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
from adafruit_lsm6ds import Rate
import time
import board
import busio
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

def main() -> None:
    """Main function to read sensor data and print it in JSON format.

    This function connects to the ISM330DHCX sensor and continuously reads
    acceleration and angular velocity data. The data is then formatted into
    JSON strings and printed. If a connection error occurs, it attempts to
    reconnect to the sensor after a specified wait time.

    Raises:
        OSError: If an error occurs during sensor data reading or connection.

    """
    i2c = busio.I2C(board.RX, board.TX)
    sensor = connect_to_sensor(i2c=i2c)

    # This assumes two things:
    # 1. We care about the more precise data possibly (e.g. power by damned)
    # 2. That actually checking the sensor takes roughly 0 time
    wait_between_payloads_seconds = (1000 / get_sample_rate(sensor)) / 1000
    last_acceleration = None

    while True:
        try:
            if sensor is None:
                sensor = connect_to_sensor(i2c=i2c)

            # M/s^2
            # TODO: Maybe only send if the change is meaningful compared to the previous value
            # (e.g. 0.1 M/s^2)
            current_acceleration = sensor.acceleration

            if last_acceleration is None:
                # First iteration: print the reading and set as last reading.
                print(form_tuple_payload(constants.ACCELERATION, current_acceleration))
                last_acceleration = current_acceleration
            else:
                MINIMUM_CHANGE = 0.1
                # Check if any axis changed by more than 0.1
                if (abs(current_acceleration[0] - last_acceleration[0]) > MINIMUM_CHANGE or
                    abs(current_acceleration[1] - last_acceleration[1]) > MINIMUM_CHANGE or
                    abs(current_acceleration[2] - last_acceleration[2]) > MINIMUM_CHANGE):
                    
                    print(form_tuple_payload(ACCELERATION, current_acceleration))
                    last_acceleration = current_acceleration


            # radian/s
            # print(form_tuple_payload("angular_velocity", sensor.gyro))

            # This also has a `temperature` field but I'm not sure if that's chip temperature or ambient
            time.sleep(wait_between_payloads_seconds)
        except (OSError) as e:
            sensor = None
            time.sleep(WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS)
        except BaseException as e:
            raise e

main()