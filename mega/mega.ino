#include <ADXL345_WE.h>
#include <SPI.h>
#include <math.h>

// --- PIN TANIMLAMALARI ---
#define CS_PIN1 4  // O_L (Sol Omuz)
#define CS_PIN2 6  // O_R (Sağ Omuz)
#define CS_PIN3 2  // S_1 (Üst Omurga)
#define CS_PIN4 9  // S_2
#define CS_PIN5 7  // S_3
#define CS_PIN6 3  // S_4
#define CS_PIN7 5  // S_5 (Alt Bel)

const int sensorPins[] = {A3, A0, A1, A2, A6};
const int noktaPins[]  = {A4, A5, A10, A7, A8, A9, A11, A12, A13};
const int csPins[]     = {CS_PIN1, CS_PIN2, CS_PIN3, CS_PIN4, CS_PIN5, CS_PIN6, CS_PIN7};

// --- FİLTRE AYARLARI ---
float imuAlpha = 0.45;
float sP[7] = {0}, sR[7] = {0};

float FSR_GAIN = 3.5;
float FSR_DEADZONE = 0.08;
float fsrAlpha = 0.3;
float filteredLeft[5] = {0};
float filteredRight[9] = {0};

unsigned long lastTime = 0;

// Sensör Nesneleri
ADXL345_WE myAcc1 = ADXL345_WE(CS_PIN1, true);
ADXL345_WE myAcc2 = ADXL345_WE(CS_PIN2, true);
ADXL345_WE myAcc3 = ADXL345_WE(CS_PIN3, true);
ADXL345_WE myAcc4 = ADXL345_WE(CS_PIN4, true);
ADXL345_WE myAcc5 = ADXL345_WE(CS_PIN5, true);
ADXL345_WE myAcc6 = ADXL345_WE(CS_PIN6, true);
ADXL345_WE myAcc7 = ADXL345_WE(CS_PIN7, true);

ADXL345_WE* sensors[7] = {&myAcc1, &myAcc2, &myAcc3, &myAcc4, &myAcc5, &myAcc6, &myAcc7};

void setup() {
  Serial.begin(115200);
  Serial1.begin(115200);
  delay(50);

  // KRİTİK: Tüm CS pinleri SPI.begin()'den ÖNCE HIGH yapılmalı.
  // Aksi halde sensörler yüzer hatta hep birlikte yanıt verir ve ilk SPI transferi kilitlenir.
  for (int i = 0; i < 7; i++) {
    pinMode(csPins[i], OUTPUT);
    digitalWrite(csPins[i], HIGH);
  }

  SPI.begin();
  delay(100);

  // Tanılama çıktılı init — hangi sensör başarısızsa Serial monitor'de görünür
  for (int i = 0; i < 7; i++) {
    if (!sensors[i]->init()) {
      Serial.print(F("HATA: ACC"));
      Serial.print(i + 1);
      Serial.print(F(" (CS pin "));
      Serial.print(csPins[i]);
      Serial.println(F(") init basarisiz"));
      while (1) { delay(1000); }
    }
    sensors[i]->setMeasureMode(true);
  }

  Serial.println(F("Tum sensorler OK — veri akisi basliyor"));
}

void loop() {
  // 50ms = 20Hz kesintisiz akış
  if (millis() - lastTime > 50) {
    lastTime = millis();
    xyzFloat v[7];

    // 1. Tüm IMU'ları oku
    for (int i = 0; i < 7; i++) {
      sensors[i]->getGValues(&v[i]);

      float rP = atan2(v[i].y, v[i].z) * 57.295779;
      float rR = atan2(-v[i].x, sqrt(v[i].y * v[i].y + v[i].z * v[i].z)) * 57.295779;

      sP[i] = (sP[i] * (1.0 - imuAlpha)) + (rP * imuAlpha);
      sR[i] = (sR[i] * (1.0 - imuAlpha)) + (rR * imuAlpha);
    }

    // 2. FSR oku ve filtrele (10-bit ADC: 0..1023)
    for (int i = 0; i < 5; i++) {
      float rawL = (analogRead(sensorPins[i]) / 1023.0) * FSR_GAIN;
      filteredLeft[i] = (filteredLeft[i] * (1.0 - fsrAlpha)) + (rawL * fsrAlpha);
    }
    for (int i = 0; i < 9; i++) {
      float rawR = (analogRead(noktaPins[i]) / 1023.0) * FSR_GAIN;
      filteredRight[i] = (filteredRight[i] * (1.0 - fsrAlpha)) + (rawR * fsrAlpha);
    }

    // 3. JSON paketle — reserve() ile RAM fragmentasyonu önlenir
    String payload;
    payload.reserve(320);

    payload += F("{\"IMU\":[");
    for (int i = 0; i < 7; i++) {
      payload += String(sP[i], 1);
      payload += ',';
      payload += String(sR[i], 1);
      if (i < 6) payload += ',';
    }

    payload += F("],\"FSR\":[");
    for (int i = 0; i < 5; i++) {
      float fL = (filteredLeft[i] < FSR_DEADZONE) ? 0.0 : min(filteredLeft[i], 1.0f);
      payload += String(fL, 2);
      if (i < 4) payload += ',';
    }

    payload += F("],\"NOK\":[");
    for (int i = 0; i < 9; i++) {
      float fR = (filteredRight[i] < FSR_DEADZONE) ? 0.0 : min(filteredRight[i], 1.0f);
      payload += String(fR, 2);
      if (i < 8) payload += ',';
    }
    payload += F("]}");

    // 4. ESP32'ye gönder
    Serial1.println(payload);
  }
}
