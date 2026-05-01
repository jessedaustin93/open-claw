#include <Arduino.h>

// Aeon-V1 dedicated auth device.
//
// USB protocol: newline-delimited JSON over native ESP32-S3 USB CDC.
// Host sends: {"type":"approval_request","id":"abc123","summary":"semantic memory write","expires_ms":30000}
// Button hold sends: {"type":"approval","id":"abc123","approved":true,"method":"button_hold","held_ms":1200}

namespace {

constexpr const char *DEVICE_NAME = "open-claw-auth";
constexpr const char *FIRMWARE_VERSION = "1.0.0";

// Most ESP32-S3 dev boards expose GPIO0 as the BOOT button, active-low.
constexpr uint8_t BUTTON_PIN = 0;
constexpr uint8_t LED_PIN = 48;

constexpr uint32_t DEBOUNCE_MS = 35;
constexpr uint32_t APPROVAL_HOLD_MS = 1000;
constexpr uint32_t DEFAULT_EXPIRES_MS = 30000;
constexpr size_t RX_LIMIT = 384;

struct PendingApproval {
  bool active = false;
  char id[65] = {0};
  char summary[161] = {0};
  uint32_t requestedAt = 0;
  uint32_t expiresMs = DEFAULT_EXPIRES_MS;
};

PendingApproval pending;
char rxBuffer[RX_LIMIT];
size_t rxLen = 0;

bool lastRawButton = true;
bool stableButton = true;
uint32_t lastBounceAt = 0;
uint32_t pressedAt = 0;
bool approvalSentForPress = false;
bool requireReleaseBeforeApproval = false;
uint32_t lastBlinkAt = 0;
bool ledState = false;

void jsonEscapePrint(const char *value) {
  Serial.print('"');
  for (const char *p = value; *p; ++p) {
    switch (*p) {
      case '"': Serial.print("\\\""); break;
      case '\\': Serial.print("\\\\"); break;
      case '\n': Serial.print("\\n"); break;
      case '\r': Serial.print("\\r"); break;
      case '\t': Serial.print("\\t"); break;
      default:
        if (static_cast<uint8_t>(*p) < 0x20) {
          Serial.print(' ');
        } else {
          Serial.print(*p);
        }
    }
  }
  Serial.print('"');
}

void sendHello() {
  Serial.print("{\"type\":\"hello\",\"device\":");
  jsonEscapePrint(DEVICE_NAME);
  Serial.print(",\"version\":");
  jsonEscapePrint(FIRMWARE_VERSION);
  Serial.print(",\"button_pin\":");
  Serial.print(BUTTON_PIN);
  Serial.println(",\"capabilities\":[\"physical_approval\",\"button_hold\"]}");
}

void sendStatus() {
  Serial.print("{\"type\":\"status\",\"device\":");
  jsonEscapePrint(DEVICE_NAME);
  Serial.print(",\"pending\":");
  Serial.print(pending.active ? "true" : "false");
  if (pending.active) {
    Serial.print(",\"id\":");
    jsonEscapePrint(pending.id);
  }
  Serial.println("}");
}

void sendError(const char *message) {
  Serial.print("{\"type\":\"error\",\"message\":");
  jsonEscapePrint(message);
  Serial.println("}");
}

bool extractJsonString(const char *json, const char *key, char *out, size_t outSize) {
  if (outSize == 0) {
    return false;
  }
  out[0] = '\0';

  char pattern[40];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char *keyPos = strstr(json, pattern);
  if (!keyPos) {
    return false;
  }
  const char *colon = strchr(keyPos + strlen(pattern), ':');
  if (!colon) {
    return false;
  }
  const char *start = strchr(colon, '"');
  if (!start) {
    return false;
  }
  ++start;

  size_t written = 0;
  bool escaping = false;
  for (const char *p = start; *p; ++p) {
    char c = *p;
    if (escaping) {
      switch (c) {
        case 'n': c = '\n'; break;
        case 'r': c = '\r'; break;
        case 't': c = '\t'; break;
        default: break;
      }
      escaping = false;
    } else if (c == '\\') {
      escaping = true;
      continue;
    } else if (c == '"') {
      out[written] = '\0';
      return true;
    }

    if (written + 1 < outSize) {
      out[written++] = c;
    }
  }

  out[written] = '\0';
  return false;
}

uint32_t extractJsonUInt(const char *json, const char *key, uint32_t fallback) {
  char pattern[40];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char *keyPos = strstr(json, pattern);
  if (!keyPos) {
    return fallback;
  }
  const char *colon = strchr(keyPos + strlen(pattern), ':');
  if (!colon) {
    return fallback;
  }
  while (*(++colon) == ' ') {
  }
  if (!isdigit(static_cast<unsigned char>(*colon))) {
    return fallback;
  }
  return static_cast<uint32_t>(strtoul(colon, nullptr, 10));
}

void startApprovalRequest(const char *line) {
  char id[sizeof(pending.id)];
  if (!extractJsonString(line, "id", id, sizeof(id)) || id[0] == '\0') {
    sendError("approval_request requires a non-empty id");
    return;
  }

  extractJsonString(line, "summary", pending.summary, sizeof(pending.summary));
  strncpy(pending.id, id, sizeof(pending.id) - 1);
  pending.id[sizeof(pending.id) - 1] = '\0';
  pending.expiresMs = extractJsonUInt(line, "expires_ms", DEFAULT_EXPIRES_MS);
  if (pending.expiresMs < APPROVAL_HOLD_MS + 500) {
    pending.expiresMs = APPROVAL_HOLD_MS + 500;
  }
  pending.requestedAt = millis();
  pending.active = true;
  approvalSentForPress = false;
  requireReleaseBeforeApproval = stableButton == LOW;
  pressedAt = stableButton == LOW ? millis() : 0;

  Serial.print("{\"type\":\"armed\",\"id\":");
  jsonEscapePrint(pending.id);
  Serial.print(",\"expires_ms\":");
  Serial.print(pending.expiresMs);
  Serial.println("}");
}

void cancelApproval(const char *line) {
  char id[sizeof(pending.id)];
  extractJsonString(line, "id", id, sizeof(id));
  if (!pending.active || id[0] == '\0' || strcmp(id, pending.id) == 0) {
    pending.active = false;
    requireReleaseBeforeApproval = false;
    digitalWrite(LED_PIN, LOW);
    ledState = false;
    Serial.println("{\"type\":\"cancelled\"}");
  }
}

void sendApproval(uint32_t heldMs) {
  if (!pending.active) {
    return;
  }
  Serial.print("{\"type\":\"approval\",\"id\":");
  jsonEscapePrint(pending.id);
  Serial.print(",\"approved\":true,\"method\":\"button_hold\",\"held_ms\":");
  Serial.print(heldMs);
  Serial.println("}");
  pending.active = false;
  requireReleaseBeforeApproval = false;
  digitalWrite(LED_PIN, LOW);
  ledState = false;
}

void expireIfNeeded() {
  if (!pending.active) {
    return;
  }
  if (millis() - pending.requestedAt >= pending.expiresMs) {
    Serial.print("{\"type\":\"expired\",\"id\":");
    jsonEscapePrint(pending.id);
    Serial.println("}");
    pending.active = false;
    requireReleaseBeforeApproval = false;
    digitalWrite(LED_PIN, LOW);
    ledState = false;
  }
}

void handleLine(char *line) {
  if (strstr(line, "\"type\":\"approval_request\"") || strstr(line, "\"type\": \"approval_request\"")) {
    startApprovalRequest(line);
  } else if (strstr(line, "\"type\":\"cancel\"") || strstr(line, "\"type\": \"cancel\"")) {
    cancelApproval(line);
  } else if (strstr(line, "\"type\":\"status\"") || strstr(line, "\"type\": \"status\"")) {
    sendStatus();
  } else if (strstr(line, "\"type\":\"hello\"") || strstr(line, "\"type\": \"hello\"")) {
    sendHello();
  } else {
    sendError("unknown message type");
  }
}

void readSerial() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      rxBuffer[rxLen] = '\0';
      if (rxLen > 0) {
        handleLine(rxBuffer);
      }
      rxLen = 0;
    } else if (c != '\r') {
      if (rxLen + 1 < RX_LIMIT) {
        rxBuffer[rxLen++] = c;
      } else {
        rxLen = 0;
        sendError("message too long");
      }
    }
  }
}

void updateButton() {
  const bool raw = digitalRead(BUTTON_PIN);
  if (raw != lastRawButton) {
    lastRawButton = raw;
    lastBounceAt = millis();
  }

  if (millis() - lastBounceAt < DEBOUNCE_MS || raw == stableButton) {
    return;
  }

  stableButton = raw;
  const bool pressed = stableButton == LOW;
  if (pressed) {
    pressedAt = millis();
    approvalSentForPress = false;
  } else {
    pressedAt = 0;
    requireReleaseBeforeApproval = false;
  }
}

void checkApprovalHold() {
  if (!pending.active || stableButton != LOW || approvalSentForPress || requireReleaseBeforeApproval) {
    return;
  }
  const uint32_t heldMs = millis() - pressedAt;
  if (heldMs >= APPROVAL_HOLD_MS) {
    approvalSentForPress = true;
    sendApproval(heldMs);
  }
}

void updateLed() {
  if (!pending.active) {
    digitalWrite(LED_PIN, LOW);
    ledState = false;
    return;
  }

  const uint32_t interval = stableButton == LOW ? 90 : 350;
  if (millis() - lastBlinkAt >= interval) {
    lastBlinkAt = millis();
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
  }
}

}  // namespace

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  delay(800);
  sendHello();
}

void loop() {
  readSerial();
  updateButton();
  checkApprovalHold();
  expireIfNeeded();
  updateLed();
  delay(5);
}
