#include <WiFi.h>
#include <WiFiUdp.h>
#include <EmonLib.h>

#define CURRENT_PIN 34
#define CALIBRATION 60.6    // Fine tune if needed
#define VOLTAGE 230.0      // Assume constant 230V AC
#define UDP_PORT 5005
#define UPDATE_RATE_MS 1000
#define SERVER_IP "192.168.1.100"  // Replace with actual server IP

EnergyMonitor emon1;
WiFiUDP udp;

void connectToWiFi() {
  WiFi.begin("ANJANSONI", "123456789");
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
