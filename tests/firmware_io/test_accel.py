
import json
import sys
import types
from types import SimpleNamespace

import pytest

if "adafruit_lis2mdl" not in sys.modules:
    lis2mdl = types.ModuleType("adafruit_lis2mdl")
    lis2mdl.LIS2MDL = object
    sys.modules["adafruit_lis2mdl"] = lis2mdl

if "adafruit_lsm6ds" not in sys.modules:
    lsm6ds = types.ModuleType("adafruit_lsm6ds")

    class _FakeRate:
        RATE_104_HZ = "RATE_104_HZ"
        string = {"RATE_104_HZ": 0.0}

    lsm6ds.Rate = _FakeRate
    sys.modules["adafruit_lsm6ds"] = lsm6ds
else:
    lsm6ds = sys.modules["adafruit_lsm6ds"]

if "adafruit_lsm6ds.ism330dhcx" not in sys.modules:
    ism_module = types.ModuleType("adafruit_lsm6ds.ism330dhcx")
    ism_module.ISM330DHCX = object
    sys.modules["adafruit_lsm6ds.ism330dhcx"] = ism_module
    setattr(lsm6ds, "ism330dhcx", ism_module)

if "adafruit_lsm303_accel" not in sys.modules:
    lsm303 = types.ModuleType("adafruit_lsm303_accel")
    lsm303.LSM303_Accel = object
    sys.modules["adafruit_lsm303_accel"] = lsm303

from helpers.firmware_io import StubSensor

from heart.firmware_io import accel, constants


@pytest.mark.parametrize(
    "sequence, expected",
    [
        (
            [
                {"accel": (0.0, 0.0, 0.0), "gyro": (0.0, 0.0, 0.0)},
                {"accel": (0.05, 0.02, 0.0), "gyro": (0.05, 0.0, 0.0)},
                {"accel": (0.3, 0.0, 0.0), "gyro": (0.12, 0.0, 0.0)},
            ],
            [
                [
                    accel.form_tuple_payload(constants.ACCELERATION, (0.0, 0.0, 0.0)),
                    accel.form_tuple_payload(constants.GYROSCOPE, (0.0, 0.0, 0.0)),
                ],
                [],
                [
                    accel.form_tuple_payload(constants.ACCELERATION, (0.3, 0.0, 0.0)),
                    accel.form_tuple_payload(constants.GYROSCOPE, (0.12, 0.0, 0.0)),
                ],
            ],
        ),
    ],
)
def test_sensor_reader_emits_payloads_when_values_change(sequence, expected) -> None:
    sensor = StubSensor(acceleration=sequence[0]["accel"], gyro=sequence[0]["gyro"])
    reader = accel.SensorReader([sensor], min_change=0.1)

    captured: list[list[str]] = []
    for step in sequence:
        sensor.acceleration = step["accel"]
        sensor.gyro = step["gyro"]
        captured.append(list(reader.read()))

    assert captured == expected


@pytest.mark.parametrize(
    "new, old, threshold, expected",
    [
        ((0.0, 0.0, 0.0), None, 0.1, True),
        ((0.05, 0.0, 0.0), (0.0, 0.0, 0.0), 0.1, False),
        ((0.2, 0.0, 0.0), (0.0, 0.0, 0.0), 0.1, True),
    ],
)
def test_changed_enough_respects_threshold(new, old, threshold, expected) -> None:
    reader = accel.SensorReader([])
    assert reader._changed_enough(new, old, threshold) is expected


@pytest.mark.parametrize(
    "sensor_kwargs, expected_key",
    [
        ({"accelerometer_data_rate": "RATE_52_HZ"}, "RATE_52_HZ"),
        ({}, "RATE_104_HZ"),
    ],
)
def test_get_sample_rate_falls_back_to_default(monkeypatch, sensor_kwargs, expected_key) -> None:
    class FakeRate:
        RATE_104_HZ = "RATE_104_HZ"
        string = {
            "RATE_104_HZ": 9.6,
            "RATE_52_HZ": 19.2,
        }

    monkeypatch.setattr(accel, "Rate", FakeRate)

    sensor = SimpleNamespace(**sensor_kwargs)
    reader = accel.SensorReader([])

    assert reader.get_sample_rate(sensor) == FakeRate.string[expected_key]


@pytest.mark.parametrize(
    "payload",
    [
        ((1.0, 2.0, 3.0),),
        ((-0.1, 0.0, 9.81),),
    ],
)
def test_form_tuple_payload_wraps_json_in_newlines(payload) -> None:
    result = accel.form_tuple_payload(constants.ACCELERATION, payload[0])
    assert result.startswith("\n") and result.endswith("\n")
    parsed = json.loads(result.strip())
    assert parsed == {
        "event_type": constants.ACCELERATION,
        "producer_id": 0,
        "data": {
            "value": {
                "x": payload[0][0],
                "y": payload[0][1],
                "z": payload[0][2],
            }
        },
    }