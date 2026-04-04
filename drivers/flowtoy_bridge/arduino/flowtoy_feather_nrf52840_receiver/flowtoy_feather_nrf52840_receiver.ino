#include <stdint.h>
#include <stdlib.h>
#include <strings.h>
#include <string.h>

#include <nrf_to_nrf.h>

constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long SERIAL_WAIT_TIMEOUT_MS = 2000;
constexpr unsigned long IDLE_DELAY_MS = 5;
constexpr uint8_t FLOWTOY_CHANNEL = 2;
constexpr uint8_t FLOWTOY_ADDRESS_WIDTH_BYTES = 3;
constexpr uint8_t FLOWTOY_SYNC_PACKET_SIZE = 21;
constexpr uint8_t RADIO_READ_BUFFER_SIZE = 32;
constexpr uint8_t SERIAL_COMMAND_BUFFER_SIZE = 128;
constexpr uint8_t FLOWTOY_ADDRESS[5] = {0x01, 0x07, 0xF1, 0x00, 0x00};
constexpr char DEVICE_NAME[] = "feather-flowtoy-bridge";
constexpr char DEVICE_ID[] = "manual-feather-flowtoy-bridge";
constexpr char FIRMWARE_COMMIT[] = "MANUAL-ARDUINO-NRF52";

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

nrf_to_nrf radio;
uint32_t nextPadding = 1;

uint16_t encodeGroupId(const uint16_t groupId) {
  return static_cast<uint16_t>(((groupId & 0xFF) << 8) | ((groupId >> 8) & 0xFF));
}

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
  radio.openWritingPipe(FLOWTOY_ADDRESS);
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
  Serial.print("\"mode\":\"transmit-receive\",");
  Serial.print("\"runtime\":\"arduino-nrf52\",");
  Serial.print("\"radio_backend\":\"nrf_to_nrf\"}}\n");
}

uint8_t parseByteValue(char *token) {
  if (token == nullptr || token[0] == '\0') {
    return 0;
  }
  return static_cast<uint8_t>(strtoul(token, nullptr, 10));
}

uint16_t parseGroupId(char *token) {
  if (token == nullptr || token[0] == '\0') {
    return 0;
  }
  return static_cast<uint16_t>(strtoul(token, nullptr, 10));
}

void transmitPacket(const SyncPacket &packet) {
  SyncPacket packetToSend = packet;
  radio.stopListening();
  radio.write(&packetToSend, sizeof(SyncPacket));
  radio.startListening();
}

void emitCommandResult(const char *command, const SyncPacket &packet) {
  Serial.print("{\"event_type\":\"peripheral.radio.command.sent\",\"data\":{");
  Serial.print("\"command\":\"");
  Serial.print(command);
  Serial.print("\",\"group_id\":");
  Serial.print(static_cast<uint16_t>((packet.groupID >> 8 & 0xFF) | ((packet.groupID & 0xFF) << 8)));
  Serial.print(",\"page\":");
  Serial.print(packet.page);
  Serial.print(",\"mode\":");
  Serial.print(packet.mode);
  Serial.print(",\"padding\":");
  Serial.print(packet.padding);
  Serial.print("}}\n");
}

void handlePatternCommand(char command, char *message) {
  SyncPacket packet{};
  char *token = strtok(message + 1, ",");
  packet.groupID = encodeGroupId(parseGroupId(token));
  token = strtok(nullptr, ",");
  packet.page = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.mode = parseByteValue(token);
  token = strtok(nullptr, ",");
  const uint8_t actives = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.global_hue = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.global_sat = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.global_val = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.global_speed = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.global_density = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.lfo[0] = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.lfo[1] = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.lfo[2] = parseByteValue(token);
  token = strtok(nullptr, ",");
  packet.lfo[3] = parseByteValue(token);
  packet.padding = nextPadding++;
  packet.lfo_active = actives & 1;
  packet.hue_active = (actives >> 1) & 1;
  packet.sat_active = (actives >> 2) & 1;
  packet.val_active = (actives >> 3) & 1;
  packet.speed_active = (actives >> 4) & 1;
  packet.density_active = (actives >> 5) & 1;
  transmitPacket(packet);
  emitCommandResult(command == 'P' ? "P" : "p", packet);
}

void handleWakePowerCommand(char command, char *message) {
  SyncPacket packet{};
  packet.groupID = encodeGroupId(parseGroupId(message + 1));
  packet.padding = nextPadding++;
  if (command == 'w' || command == 'W') {
    packet.wakeup = 1;
  } else {
    packet.poweroff = 1;
  }
  transmitPacket(packet);
  if (command == 'w' || command == 'W') {
    emitCommandResult(command == 'W' ? "W" : "w", packet);
  } else {
    emitCommandResult(command == 'Z' ? "Z" : "z", packet);
  }
}

void handleSerialInput() {
  static char buffer[SERIAL_COMMAND_BUFFER_SIZE];
  static size_t index = 0;

  while (Serial.available()) {
    const char value = static_cast<char>(Serial.read());
    if (value == '\n' || value == '\r') {
      buffer[index] = '\0';
      if (index > 0) {
        if (strcasecmp(buffer, "identify") == 0) {
          emitIdentify();
        } else {
          switch (buffer[0]) {
            case 'p':
            case 'P':
              handlePatternCommand(buffer[0], buffer);
              break;
            case 'w':
            case 'W':
            case 'z':
            case 'Z':
              handleWakePowerCommand(buffer[0], buffer);
              break;
            default:
              break;
          }
        }
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
  handleSerialInput();

  if (radio.available()) {
    const uint8_t payloadSize = radio.getPayloadSize();
    uint8_t payload[RADIO_READ_BUFFER_SIZE];
    const size_t bytesToRead = payloadSize > sizeof(payload) ? sizeof(payload) : payloadSize;
    radio.read(&payload, bytesToRead);
    emitPacket(payload, bytesToRead);
  } else {
    delay(IDLE_DELAY_MS);
  }
}
