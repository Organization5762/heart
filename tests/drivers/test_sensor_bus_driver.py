import json

from driver_loader import load_driver_module, make_module

from heart.firmware_io import constants


class FakeRate:
    RATE_104_HZ = "104"
    RATE_208_HZ = "208"
    string = {RATE_104_HZ: 104.0, RATE_208_HZ: 208.0}


STUBS = {
    "board": make_module("board"),
    "adafruit_lis2mdl": make_module("adafruit_lis2mdl", LIS2MDL=object),
    "adafruit_lsm6ds": make_module("adafruit_lsm6ds", Rate=FakeRate),
    "adafruit_lsm6ds.ism330dhcx": make_module(
        "adafruit_lsm6ds.ism330dhcx", ISM330DHCX=object
    ),
    "adafruit_lsm303_accel": make_module("adafruit_lsm303_accel", LSM303_Accel=object),
}

sensor_bus = load_driver_module("sensor_bus", stubs=STUBS)


class StubAccelerationSensor:
    def __init__(self, acceleration):
        self._values = list(acceleration)
        self._index = 0
        self.current = self._values[0]

    def step(self):
        if self._index + 1 < len(self._values):
            self._index += 1
        self.current = self._values[self._index]

    @property
    def acceleration(self):
        return self.current


class StubGyroSensor:
    def __init__(self, gyro):
        self._values = list(gyro)
        self._index = 0
        self.current = self._values[0]

    def step(self):
        if self._index + 1 < len(self._values):
            self._index += 1
        self.current = self._values[self._index]

    @property
    def gyro(self):
        return self.current


def test_form_tuple_payload_returns_json():
    payload = sensor_bus.form_tuple_payload("rotation", (1.0, 2.0, 3.0))
    assert payload.startswith("\n")
    decoded = json.loads(payload.strip())
    assert decoded == {"event_type": "rotation", "data": {"x": 1.0, "y": 2.0, "z": 3.0}}


def test_get_sample_rate_prefers_sensor_value():
    class Stub:
        accelerometer_data_rate = sensor_bus.Rate.RATE_208_HZ

    assert sensor_bus.get_sample_rate(Stub()) == sensor_bus.Rate.string[Stub.accelerometer_data_rate]


def test_get_sample_rate_defaults_when_missing():
    class Stub:
        pass

    assert sensor_bus.get_sample_rate(Stub()) == sensor_bus.Rate.string[sensor_bus.Rate.RATE_104_HZ]


def test_connect_to_sensors_skips_failures(monkeypatch):
    created = []

    class GoodSensor:
        def __init__(self, i2c):
            created.append((self.__class__.__name__, i2c))

    class BadSensor:
        def __init__(self, i2c):
            raise RuntimeError("boom")

    monkeypatch.setattr(sensor_bus, "LSM303_Accel", GoodSensor)
    monkeypatch.setattr(sensor_bus, "LIS2MDL", BadSensor)
    monkeypatch.setattr(sensor_bus, "ISM330DHCX", GoodSensor)

    sensors = sensor_bus.connect_to_sensors("i2c-bus")
    assert len(sensors) == 2
    assert created == [("GoodSensor", "i2c-bus"), ("GoodSensor", "i2c-bus")]


def test_sensor_reader_emits_when_change_exceeds_threshold():
    accel_sensor = StubAccelerationSensor(
        acceleration=[
            (0.0, 0.0, 0.0),
            (0.05, 0.0, 0.05),
            (0.05, 0.0, 0.25),
            (0.05, 0.0, 0.25),
        ],
    )
    gyro_sensor = StubGyroSensor(
        gyro=[
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.05),
            (0.0, 0.0, 0.3),
            (0.0, 0.0, 0.3),
        ]
    )
    reader = sensor_bus.SensorReader([accel_sensor, gyro_sensor], min_change=0.1)

    first = list(reader.read())
    accel_sensor.step()
    gyro_sensor.step()
    second = list(reader.read())
    accel_sensor.step()
    gyro_sensor.step()
    third = list(reader.read())

    assert constants.ACCELERATION in first[0]
    assert constants.GYROSCOPE in first[1]
    assert second == []
    assert len(third) == 2
    accel_payload = json.loads(third[0].strip())
    gyro_payload = json.loads(third[1].strip())
    assert accel_payload["event_type"] == constants.ACCELERATION
    assert gyro_payload["event_type"] == constants.GYROSCOPE
