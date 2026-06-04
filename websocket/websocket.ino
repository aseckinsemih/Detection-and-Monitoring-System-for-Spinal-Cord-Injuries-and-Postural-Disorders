/*******************************************************
 * ESP32 WebSocket Bridge
 * Mega → Serial2 (115200) → WebSocket istemcileri (port 81)
 *
 * KRITIK NOKTALAR (sürekli bağlan/kopma sorununun çözümü):
 *   1) Serial2.readStringUntil() BLOKLAR (default 1s timeout).
 *      Mega 1Hz gönderdiği için her okuma ~1sn websocket.loop()'u
 *      starve ediyor → ping/pong timeout → kopma. Bunun yerine
 *      karakter-karakter non-blocking okuma yapılıyor.
 *   2) WiFi.reconnect() kullanılır; webSocket.begin() loop içinde
 *      asla tekrar çağrılmaz (yoksa istemciler atılır).
 *   3) Bağlantı eventleri (CONNECTED/DISCONNECTED/ERROR) loglanır.
 *******************************************************/
#include <WiFi.h>
#include <WebSocketsServer.h>

const char *ssid     = "test";
const char *password = "12345678";

#define WS_PORT      81
#define MEGA_BAUD    115200
#define RX_PIN       16
#define TX_PIN       17

WebSocketsServer webSocket = WebSocketsServer(WS_PORT);

// --- Non-blocking serial okuma için tampon ---
#define BUF_SIZE 1024
char rxBuf[BUF_SIZE];
size_t rxIdx = 0;

// --- WiFi durum takibi ---
unsigned long lastWifiCheck = 0;
const unsigned long WIFI_CHECK_INTERVAL = 5000;

// --- İstatistik (debug için) ---
unsigned long pktCount = 0;
unsigned long lastStatPrint = 0;
int activeClients = 0;

// =========================================================
// WebSocket event handler — bağlan/kopma sebebini görmek için
// =========================================================
void onWsEvent(uint8_t num, WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED: {
      IPAddress ip = webSocket.remoteIP(num);
      activeClients++;
      Serial.printf("[WS] #%u BAGLANDI: %d.%d.%d.%d (toplam: %d)\n",
                    num, ip[0], ip[1], ip[2], ip[3], activeClients);
      break;
    }
    case WStype_DISCONNECTED:
      if (activeClients > 0) activeClients--;
      Serial.printf("[WS] #%u KOPTU (toplam: %d)\n", num, activeClients);
      break;
    case WStype_ERROR:
      Serial.printf("[WS] #%u HATA\n", num);
      break;
    case WStype_PING:
      // Sessiz tut — sadece sayıyı görmek için aç
      break;
    case WStype_PONG:
      break;
    case WStype_TEXT:
      Serial.printf("[WS] #%u text geldi: %.*s\n", num, (int)length, payload);
      break;
    default:
      break;
  }
}

// =========================================================
// WiFi bağlantısı
// =========================================================
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);          // KRITIK: WiFi sleep'i kapat — paket kaybı/timeout azalır
  WiFi.begin(ssid, password);

  Serial.print("WiFi bagleniyor");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi BASARISIZ — 5sn sonra yeniden basla");
    delay(5000);
    ESP.restart();
  }

  Serial.println();
  Serial.print("[WiFi] OK | IP: ");
  Serial.print(WiFi.localIP());
  Serial.print(" | RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
}

// =========================================================
// Setup
// =========================================================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== ESP32 WS Bridge ===");

  Serial2.begin(MEGA_BAUD, SERIAL_8N1, RX_PIN, TX_PIN);

  connectWiFi();

  webSocket.begin();
  webSocket.onEvent(onWsEvent);

  // Kütüphane "heartbeat" — istemcinin hayatta olup olmadığını otomatik kontrol eder.
  // (interval, timeout, retry) — yavaş ağlarda kopmayı engeller
  webSocket.enableHeartbeat(15000, 3000, 2);

  Serial.printf("[WS] port %d hazir\n", WS_PORT);
  Serial.println("=========================");
}

// =========================================================
// Non-blocking serial okuma — bir satır biriktiğinde true döner
// =========================================================
bool readSerialLine(String &out) {
  while (Serial2.available()) {
    char c = (char)Serial2.read();

    if (c == '\r') continue;     // CR atla

    if (c == '\n') {
      if (rxIdx == 0) return false;     // boş satır
      rxBuf[rxIdx] = '\0';
      out = String(rxBuf);
      rxIdx = 0;
      return true;
    }

    if (rxIdx < BUF_SIZE - 1) {
      rxBuf[rxIdx++] = c;
    } else {
      // Tampon doldu, paketi at — büyük olasılıkla bozuk
      Serial.println("[RX] tampon dolu, paket atildi");
      rxIdx = 0;
    }
  }
  return false;
}

// =========================================================
// Loop — HİÇBİR ŞEY blocking olmamalı
// =========================================================
void loop() {
  // 1) WebSocket'i her loop'ta besle — ping/pong burada işleniyor
  webSocket.loop();

  // 2) Mega'dan gelen satırı non-blocking oku
  String line;
  if (readSerialLine(line)) {
    if (line.length() > 0) {
      webSocket.broadcastTXT(line);
      pktCount++;
    }
  }

  // 3) WiFi durumunu periyodik kontrol et — kesintisiz değil
  if (millis() - lastWifiCheck > WIFI_CHECK_INTERVAL) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] koptu, reconnect deneniyor");
      WiFi.reconnect();          // webSocket.begin() ÇAĞIRMA — istemcileri korur
    }
  }

  // 4) Her 10 saniyede bir istatistik bas (debug)
  if (millis() - lastStatPrint > 10000) {
    lastStatPrint = millis();
    Serial.printf("[STAT] pkt=%lu | istemci=%d | RSSI=%d dBm | heap=%u\n",
                  pktCount, activeClients, WiFi.RSSI(), ESP.getFreeHeap());
  }
}
