#include <stdint.h>
#include <strings.h>
#include <string.h>

#include <nrf_to_nrf.h>

constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long SERIAL_WAIT_TIMEOUT_MS = 2000;
constexpr unsigned long IDLE_DELAY_MS = 5;
constexpr uint8_t FLOWTOY_CHANNEL = 2;
constexpr uint8_t FLOWTOY_ADDRESS_WIDTH_BYTES = 3;
constexpr uint8_t FLOWTOY_SYNC_PACKET_SIZE = 21;
constexpr uint8_t FLOWTOY_ADDRESS[5] = {0x01, 0x07, 0xF1, 0x00, 0x00};
constexpr char DEVICE_NAME[] = "feather-flowtoy-bridge";
constexpr char DEVICE_ID[] = "manual-feather-flowtoy-bridge";
constexpr char FIRMWARE_COMMIT[] = "MANUAL-ARDUINO-NRF52";

nrf_to_nrf radio;

void setupRadio() {
  radio.begin();
  radio.setAutoAck(false);
  radio.setDataRate(NRF_250KBPS);
  radio.setChannel(FLOWTOY_CHANNEL);
  radio.setAddressWidth(FLOWTOY_ADDRESS_WIDTH_BYTES);
  radio.setPayloadSize(FLOWTOY_SYNC_PACKET_SIZE);
  radio.setCRCLength(NRF_CRC_16);
  radio.setPALevel(NRF_PA_MAX);
  radio.openReadingPipe(1, FLOWTOY_ADDRESS);
  radio.startListening();
}

void emitIdentify() {
  Serial.print("{\"event_type\":\"device.identify\",\"data\":{");
  Serial.print("\"device_name\":\"");
  Serial.print(DEVICE_NAME);
  Serial.print("\",\"firmware_commit\":\"");
  Serial.print(FIRMWARE_COMMIT);
  Serial.print("\",\"device_id\":\"");
  Serial.print(DEVICE_ID);
  Serial.print("\",\"protocol\":\"flowtoy\",");
  Serial.print("\"mode\":\"receive-only\",");
  Serial.print("\"runtime\":\"arduino-nrf52\",");
  Serial.print("\"radio_backend\":\"nrf_to_nrf\"}}\n");
}

void handleIdentifyQuery() {
  static char buffer[64];
  static size_t index = 0;

  while (Serial.available()) {
    const char value = static_cast<char>(Serial.read());
    if (value == '\n' || value == '\r') {
      buffer[index] = '\0';
      if (strcasecmp(buffer, "identify") == 0) {
        emitIdentify();
      }
      index = 0;
      continue;
    }

    if (index + 1 < sizeof(buffer)) {
      buffer[index++] = value;
    }
  }
}

void emitPacket(const uint8_t *payload, size_t payloadSize) {
  Serial.print("{\"event_type\":\"peripheral.radio.packet\",\"data\":{");
  Serial.print("\"protocol\":\"flowtoy\",");
  Serial.print("\"channel\":");
  Serial.print(FLOWTOY_CHANNEL);
  Serial.print(",\"bitrate_kbps\":250,");
  Serial.print("\"modulation\":\"nrf24-shockburst\",");
  Serial.print("\"crc_ok\":true,");
  Serial.print("\"rssi_dbm\":");
  Serial.print(-static_cast<int16_t>(radio.getRSSI()));
  Serial.print(",\"payload\":[");
  for (size_t index = 0; index < payloadSize; ++index) {
    if (index > 0) {
      Serial.print(",");
    }
    Serial.print(payload[index]);
  }
  Serial.print("],\"metadata\":{");
  Serial.print("\"address\":[1,7,241],");
  Serial.print("\"address_width_bytes\":");
  Serial.print(FLOWTOY_ADDRESS_WIDTH_BYTES);
  Serial.print(",\"crc_bits\":16,");
  Serial.print("\"packet_size_bytes\":");
  Serial.print(payloadSize);
  Serial.print(",\"receiver\":\"nrf52840\",");
  Serial.print("\"runtime\":\"arduino-nrf52\",");
  Serial.print("\"radio_backend\":\"nrf_to_nrf\"");
  Serial.print("}}}\n");
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  const unsigned long serialWaitStart = millis();
  while (!Serial && (millis() - serialWaitStart) < SERIAL_WAIT_TIMEOUT_MS) {
  }
  setupRadio();
  emitIdentify();
}

void loop() {
  handleIdentifyQuery();

  if (radio.available()) {
    const uint8_t payloadSize = radio.getPayloadSize();
    uint8_t payload[FLOWTOY_SYNC_PACKET_SIZE];
    if (payloadSize == FLOWTOY_SYNC_PACKET_SIZE) {
      radio.read(&payload, payloadSize);
      emitPacket(payload, payloadSize);
    } else {
      uint8_t ignoredPayload[32];
      radio.read(&ignoredPayload, payloadSize > sizeof(ignoredPayload)
                                      ? sizeof(ignoredPayload)
                                      : payloadSize);
    }
  } else {
    delay(IDLE_DELAY_MS);
  }
}
