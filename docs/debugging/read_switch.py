import json

import serial

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

ser = serial.Serial("/dev/ttyACM0", 115200)

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode("utf-8").rstrip()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                logger.info("%s", data)
                continue

            event_type = payload.get("event_type")
            event_data = payload.get("data")
            producer_id = payload.get("producer_id")
            if event_type is None:
                logger.info("%s", payload)
                continue

            logger.info(
                "event=%s data=%s producer=%s",
                event_type,
                event_data,
                producer_id,
            )
except KeyboardInterrupt:
    logger.info("Program terminated")
finally:
    ser.close()
