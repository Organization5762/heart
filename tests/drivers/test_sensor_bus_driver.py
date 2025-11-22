import io
import json

import pytest
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


@pytest.fixture()
def sensor_bus(monkeypatch, tmp_path):
    device_id_path = tmp_path / "device_id.txt"
    monkeypatch.setenv("HEART_DEVICE_ID_PATH", str(device_id_path))
    monkeypatch.setenv("HEART_DEVICE_ID", "sensor-bus-test-id")
    module = load_driver_module("sensor_bus", stubs=STUBS)
    return module


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


class TestDriversSensorBusDriver:
    """Group Drivers Sensor Bus Driver tests so drivers sensor bus driver behaviour stays reliable. This preserves confidence in drivers sensor bus driver for end-to-end scenarios."""

    def test_form_tuple_payload_returns_json(self, sensor_bus):
        """Verify that form_tuple_payload encodes sensor tuples into the expected JSON string. This keeps bus messages compatible with consumers that parse structured telemetry."""
        payload = sensor_bus.form_tuple_payload("rotation", (1.0, 2.0, 3.0))
        assert payload.startswith("\n")
        decoded = json.loads(payload.strip())
        assert decoded == {"event_type": "rotation", "data": {"x": 1.0, "y": 2.0, "z": 3.0}}



    def test_get_sample_rate_prefers_sensor_value(self, sensor_bus):
        """Verify that get_sample_rate honours the accelerometer's configured data rate when it is provided. This preserves calibration intent so sampling frequency matches device capabilities."""
        class Stub:
            accelerometer_data_rate = sensor_bus.Rate.RATE_208_HZ

        raise NotImplementedError("Bus refactor")
        assert sensor_bus.get_sample_rate(Stub()) == sensor_bus.Rate.string[Stub.accelerometer_data_rate]



    def test_get_sample_rate_defaults_when_missing(self, sensor_bus):
        """Verify that get_sample_rate falls back to the default rate when the sensor defines no preference. This ensures predictable behaviour when hardware lacks metadata."""
        class Stub:
            pass

        assert sensor_bus.get_sample_rate(Stub()) == sensor_bus.Rate.string[sensor_bus.Rate.RATE_104_HZ]



    def test_connect_to_sensors_skips_failures(self, monkeypatch, sensor_bus):
        """Verify that connect_to_sensors ignores constructors that fail and returns only the working sensors. This keeps initialization resilient so one bad component does not break the stack."""
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



    def test_sensor_reader_emits_when_change_exceeds_threshold(self, sensor_bus):
        """Verify that SensorReader yields events only when the change exceeds the configured threshold. This filters out sensor noise so downstream analytics highlight meaningful movement."""
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



    def test_respond_to_identify_query_emits_identity_payload(self, sensor_bus):
        """Verify that respond_to_identify_query prints the sensor bus identity payload. This lets maintenance tooling track which sensor assemblies are connected."""
        stream = io.StringIO("Identify\n")
        outputs: list[str] = []

        handled = sensor_bus.respond_to_identify_query(stdin=stream, print_fn=outputs.append)

        assert handled is True
        assert outputs
        payload = json.loads(outputs[0])
        assert payload["event_type"] == constants.DEVICE_IDENTIFY
        assert payload["data"]["device_name"] == sensor_bus.IDENTITY.device_name
        assert payload["data"]["device_id"] == "sensor-bus-test-id"
