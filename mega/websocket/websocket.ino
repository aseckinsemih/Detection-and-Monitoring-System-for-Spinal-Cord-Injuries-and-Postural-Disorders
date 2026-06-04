#include <WiFi.h>
#include <WebSocketsServer.h>

const char *ssid = "iPhone";      // AĞ ADINI BURAYA YAZ
const char *password = "12345678"; // AĞ ŞİFRESİNİ BURAYA YAZ

WebSocketsServer webSocket = WebSocketsServer(81);

void setup() {
  Serial.begin(115200);
  // Mega'dan verinin geldiği pinler (RX:16, TX:17)
  Serial2.begin(115200, SERIAL_8N1, 16, 17); 
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.print("ESP32 IP ADRESI: ");
  Serial.println(WiFi.localIP()); // Python arayüzündeki IP adresi budur!
  
  webSocket.begin();
}

void loop() {
  webSocket.loop();
  
  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      webSocket.broadcastTXT(data);
    }
  }
}