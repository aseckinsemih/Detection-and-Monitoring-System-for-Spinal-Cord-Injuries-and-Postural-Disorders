#include <WiFi.h>
#include <WebSocketsServer.h>

const char *ssid = "test";       // AĞ ADINI BURAYA YAZ
const char *password = "12345678"; // AĞ ŞİFRESİNİ BURAYA YAZ

WebSocketsServer webSocket = WebSocketsServer(81);

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWIFI BAGLANTI BASARISIZ — 5sn sonra yeniden baslatiliyor");
    delay(5000);
    ESP.restart();
  }

  Serial.println();
  Serial.print("ESP32 IP ADRESI: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  // Mega'dan verinin geldiği pinler (RX:16, TX:17)
  Serial2.begin(115200, SERIAL_8N1, 16, 17);

  connectWiFi();
  webSocket.begin();
}

void loop() {
  // WiFi koptuysa otomatik yeniden bağlan
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi koptu, yeniden baglaniliyor...");
    connectWiFi();
    webSocket.begin();
  }

  webSocket.loop();

  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      webSocket.broadcastTXT(data);
    }
  }
}
