#include <SPI.h>
#include <RF24.h>
#include <string.h>

// Feather nRF52840 Express host MCU with an external nRF24L01+ over SPI.
// Adjust CE/CSN to match your wiring.
constexpr uint8_t RADIO_CE_PIN = 10;
constexpr uint8_t RADIO_CSN_PIN = 9;
constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr uint8_t FLOWTOY_CHANNEL = 2;
constexpr uint8_t FLOWTOY_ADDRESS_WIDTH_BYTES = 3;
constexpr uint8_t FLOWTOY_ADDRESS[5] = {0x01, 0x07, 0xF1, 0x00, 0x00};
constexpr char DEVICE_NAME[] = "feather-flowtoy-radio-bridge";
constexpr unsigned long IDLE_DELAY_MS = 5;

#pragma pack(push, 1)
struct SyncPacket {
  uint16_t groupID;
  uint32_t padding;
  uint8_t lfo[4];
  uint8_t global_hue;
  uint8_t global_sat;
  uint8_t global_val;
  uint8_t global_speed;
  uint8_t global_density;
  uint8_t lfo_active : 1;
  uint8_t hue_active : 1;
  uint8_t sat_active : 1;
  uint8_t val_active : 1;
  uint8_t speed_active : 1;
  uint8_t density_active : 1;
  uint8_t reserved[2];
  uint8_t page;
  uint8_t mode;
  uint8_t adjust_active : 1;
  uint8_t wakeup : 1;
  uint8_t poweroff : 1;
  uint8_t force_reload : 1;
  uint8_t save : 1;
  uint8_t _delete : 1;
  uint8_t alternate : 1;
};
#pragma pack(pop)

RF24 radio(RADIO_CE_PIN, RADIO_CSN_PIN);

void setupRadio() {
  radio.begin();
  radio.setAutoAck(false);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(FLOWTOY_CHANNEL);
  radio.setAddressWidth(FLOWTOY_ADDRESS_WIDTH_BYTES);
  radio.setPayloadSize(sizeof(SyncPacket));
  radio.setCRCLength(RF24_CRC_16);
  radio.openReadingPipe(1, FLOWTOY_ADDRESS);
  radio.startListening();
}

void emitIdentify() {
  Serial.print("{\"event_type\":\"device.identify\",\"data\":{");
  Serial.print("\"device_name\":\"");
  Serial.print(DEVICE_NAME);
  Serial.print("\",\"firmware_commit\":\"MANUAL-ARDUINO\",");
  Serial.print("\"device_id\":\"manual-feather-radio-bridge\",");
  Serial.print("\"protocol\":\"flowtoy\",");
  Serial.print("\"mode\":\"receive-only\"}}\n");
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

void emitPacket(const SyncPacket &packet) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&packet);

  Serial.print("{\"event_type\":\"peripheral.radio.packet\",\"data\":{");
  Serial.print("\"protocol\":\"flowtoy\",");
  Serial.print("\"channel\":");
  Serial.print(FLOWTOY_CHANNEL);
  Serial.print(",\"bitrate_kbps\":250,");
  Serial.print("\"modulation\":\"nrf24-shockburst\",");
  Serial.print("\"crc_ok\":true,");
  Serial.print("\"payload\":[");
  for (size_t index = 0; index < sizeof(SyncPacket); ++index) {
    if (index > 0) {
      Serial.print(",");
    }
    Serial.print(bytes[index]);
  }
  Serial.print("],\"metadata\":{");
  Serial.print("\"address\":[1,7,241],");
  Serial.print("\"address_width_bytes\":");
  Serial.print(FLOWTOY_ADDRESS_WIDTH_BYTES);
  Serial.print(",\"crc_bits\":16,");
  Serial.print("\"packet_size_bytes\":");
  Serial.print(sizeof(SyncPacket));
  Serial.print("}}}\n");
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  delay(200);
  setupRadio();
}

void loop() {
  handleIdentifyQuery();

  if (radio.available()) {
    SyncPacket packet;
    radio.read(&packet, sizeof(SyncPacket));
    emitPacket(packet);
  } else {
    delay(IDLE_DELAY_MS);
  }
}
