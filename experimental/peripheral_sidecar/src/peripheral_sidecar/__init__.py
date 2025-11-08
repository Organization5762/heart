"""Service layer for sidecar processes and integrations."""

from . import mqtt_sidecar as _mqtt_sidecar

PeripheralMQTTService = _mqtt_sidecar.PeripheralMQTTService

del _mqtt_sidecar
