import os
from dataclasses import dataclass


@dataclass(slots=True)
class PeripheralServiceConfig:
    """Configuration values controlling the MQTT sidecar service."""

    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: str = "heart-peripheral-sidecar"
    raw_topic: str = "heart/peripherals/raw"
    action_topic: str = "heart/peripherals/actions"
    poll_interval: float = 0.1
    mqtt_keepalive: int = 60
    raw_qos: int = 0
    action_qos: int = 1
    switch_rotation_window: float = 5.0
    switch_rotation_threshold: int = 30
    accelerometer_window: float = 2.0
    accelerometer_magnitude_threshold: float = 2.0
    heart_rate_window: float = 10.0
    heart_rate_high_threshold: int = 160
    axis_threshold: float = 0.5

    @classmethod
    def from_env(cls) -> "PeripheralServiceConfig":
        def get_env(name: str, default: str) -> str:
            return os.environ.get(name, default)

        def get_float(name: str, default: float) -> float:
            try:
                return float(get_env(name, str(default)))
            except ValueError:
                return default

        def get_int(name: str, default: int) -> int:
            try:
                return int(get_env(name, str(default)))
            except ValueError:
                return default

        return cls(
            broker_host=get_env("HEART_MQTT_HOST", "localhost"),
            broker_port=get_int("HEART_MQTT_PORT", 1883),
            client_id=get_env("HEART_MQTT_CLIENT_ID", "heart-peripheral-sidecar"),
            raw_topic=get_env("HEART_MQTT_RAW_TOPIC", "heart/peripherals/raw"),
            action_topic=get_env(
                "HEART_MQTT_ACTION_TOPIC", "heart/peripherals/actions"
            ),
            poll_interval=get_float("HEART_PERIPHERAL_POLL_INTERVAL", 0.1),
            mqtt_keepalive=get_int("HEART_MQTT_KEEPALIVE", 60),
            raw_qos=get_int("HEART_MQTT_RAW_QOS", 0),
            action_qos=get_int("HEART_MQTT_ACTION_QOS", 1),
            switch_rotation_window=get_float("HEART_SWITCH_ROTATION_WINDOW", 5.0),
            switch_rotation_threshold=get_int("HEART_SWITCH_ROTATION_THRESHOLD", 30),
            accelerometer_window=get_float("HEART_ACCEL_WINDOW", 2.0),
            accelerometer_magnitude_threshold=get_float("HEART_ACCEL_THRESHOLD", 2.0),
            heart_rate_window=get_float("HEART_HR_WINDOW", 10.0),
            heart_rate_high_threshold=get_int("HEART_HR_THRESHOLD", 160),
            axis_threshold=get_float("HEART_GAMEPAD_AXIS_THRESHOLD", 0.5),
        )
