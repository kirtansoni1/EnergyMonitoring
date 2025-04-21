#include <WiFi.h>
#include <WiFiUdp.h>
#include <EmonLib.h>

// #define CURRENT_PIN 7
#define CURRENT_PIN 7
#define CALIBRATION 60.6
#define VOLTAGE 230.0
#define UDP_PORT 8000
#define UPDATE_RATE_MS 500
#define SERVER_IP "192.168.0.149"

EnergyMonitor emon1;
WiFiUDP udp;

void connectToWiFi() {
  WiFi.begin("ANJANSONI", "1234567890");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());
}

void readVoltageCurrentSensors(void *parameter) {
  TickType_t lastWakeTime = xTaskGetTickCount();

  while (true) {
    double Irms = emon1.calcIrms(1480);
    double power = Irms * VOLTAGE;

    char buffer[128];
    snprintf(buffer, sizeof(buffer), "%.3f,%.2f", Irms, power);
    udp.beginPacket(SERVER_IP, UDP_PORT);
    udp.write((const uint8_t *)buffer, strlen(buffer));
    udp.endPacket();

    Serial.printf("Sent: I = %.3f A, P = %.2f W\n", Irms, power);
    vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(UPDATE_RATE_MS));
  }
}

void setup() {
  Serial.begin(115200);
  connectToWiFi();

  emon1.current(CURRENT_PIN, CALIBRATION);
  udp.begin(UDP_PORT);

  xTaskCreatePinnedToCore(
    readVoltageCurrentSensors,
    "CurrentTask",
    8192,
    NULL,
    3,
    NULL,
    0
  );
}

void loop() {}
