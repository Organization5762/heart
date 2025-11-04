# Heart Peripheral Sidecar (Experimental)

This experimental project packages the peripheral MQTT sidecar as a standalone
service.  It polls all detected Heart peripherals, publishes raw readings, and
emits higher-level action events to MQTT topics so that other services can
react to device activity without coupling to the hardware drivers.

## Installation

Create a virtual environment and install both `heart` and the sidecar package::

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e ../..
uv pip install -e .
```

The sidecar declares a runtime dependency on the `heart` package, so you can
substitute the local editable install for a released version when available.

## Running the service

Launch the service with::

```bash
heart-peripheral-sidecar
```

By default the service connects to an MQTT broker listening on
`localhost:1883`.  Use the provided experimental Mosquitto configuration under
`../mqtt_broker/` for local testing:

```bash
cd ../mqtt_broker
docker compose up
```

## Configuration

Tune connectivity and aggregation thresholds through environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `HEART_MQTT_HOST` | MQTT broker hostname | `localhost` |
| `HEART_MQTT_PORT` | MQTT broker TCP port | `1883` |
| `HEART_MQTT_CLIENT_ID` | Client identifier used when connecting | `heart-peripheral-sidecar` |
| `HEART_MQTT_RAW_TOPIC` | Topic where raw peripheral snapshots are published | `heart/peripherals/raw` |
| `HEART_MQTT_ACTION_TOPIC` | Topic where high-level actions are published | `heart/peripherals/actions` |
| `HEART_PERIPHERAL_POLL_INTERVAL` | Poll interval in seconds | `0.1` |
| `HEART_SWITCH_ROTATION_WINDOW` | Time window for switch rotation aggregation | `5.0` |
| `HEART_SWITCH_ROTATION_THRESHOLD` | Rotation delta needed to trigger aggregate events | `30` |
| `HEART_ACCEL_WINDOW` | Accelerometer aggregation window | `2.0` |
| `HEART_ACCEL_THRESHOLD` | Accelerometer magnitude threshold | `2.0` |
| `HEART_HR_WINDOW` | Heart rate averaging window | `10.0` |
| `HEART_HR_THRESHOLD` | Heart rate alert threshold | `160` |
| `HEART_GAMEPAD_AXIS_THRESHOLD` | Gamepad axis threshold for action triggers | `0.5` |

Raw snapshots and action messages are published as JSON payloads.  Raw samples
contain the latest values per device, while action events summarize higher-level
behaviours such as switch rotation, accelerometer movement, or heart-rate alerts
suitable for aggregation-driven triggers.
