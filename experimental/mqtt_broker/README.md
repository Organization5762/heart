# Experimental MQTT broker

This experimental setup runs a local Eclipse Mosquitto broker that the
peripheral sidecar can publish to during development.

## Requirements

- Docker (with the Compose plugin)

## Usage

```bash
cd experimental/mqtt_broker
docker compose up
```

The broker listens on:

- TCP port `1883` for MQTT clients
- TCP port `9001` for MQTT over WebSockets

Both ports are published on `localhost` and allow anonymous access for local
experimentation. Press `Ctrl+C` to stop the broker when you are finished.

## Customisation

Update `mosquitto.conf` before starting the container to tweak security or
protocol options. Any changes will be picked up on the next `docker compose up`.
