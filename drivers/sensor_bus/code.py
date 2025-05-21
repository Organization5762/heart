from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
from adafruit_lsm303_accel import LSM303_Accel
from adafruit_lis2mdl import LIS2MDL
from adafruit_lsm6ds import Rate
import time
import board
import json
from heart.firmware_io import constants, accel

WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS: float = 1.0
MIN_CHANGE = 0.5

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
    sr = accel.SensorReader.connect(i2c=i2c, min_change=MIN_CHANGE)

    # This assumes two things:
    # 1. We care about the more precise data possibly (e.g. power by damned)
    # 2. That actually checking the sensor takes roughly 0 time
    sample_rates = [
        (1000 / sr.get_sample_rate(sensor)) / 1000 for sensor in sr.sensors
    ]
    if len(sample_rates) == 0:
        wait_between_payloads_seconds = 0.1
    else:
        wait_between_payloads_seconds = min(sample_rates)
    
    while True:
        try:
            if sr is None:
                sr = accel.SensorReader.connect(i2c=i2c, min_change=MIN_CHANGE)

            for sensor_data_payload in sr.read():
                print(sensor_data_payload)

            # This also has a `temperature` field but I'm not sure if that's chip temperature or ambient
            time.sleep(wait_between_payloads_seconds)
        except (OSError) as e:
            sr = None
            time.sleep(WAIT_BEFORE_TRYING_TO_CONNECT_TO_SENSOR_SECONDS)
        except BaseException as e:
            raise e

main()