/*******************************************************
 * Mega Kodu - Sensör verilerini ayrıntılı JSON formatında gönderir
 *******************************************************/
#include <ADXL345_WE.h>
#include <SPI.h>
#include <math.h>
#include <ArduinoJson.h>

// Chip Select pinleri
#define CS_PIN1 4  // ADXL345-1
#define CS_PIN2 6  // ADXL345-2
#define CS_PIN3 2  // ADXL345-3
#define CS_PIN4 9  // ADXL345-4
#define CS_PIN5 7  // ADXL345-5
#define CS_PIN6 3  // ADXL345-6
#define CS_PIN7 5  // ADXL345-7

bool spi = true; // SPI kullanılacağını belirtir

// FSR sensör pinleri (5 adet)
const int sensorPins[] = {A0, A1, A2, A3, A6};
// Nokta sensör pinleri (9 adet)
const int noktaPins[]  = {A4, A5, A10, A7, A8, A9, A11, A12, A13};

// Sabitler
const float Vcc        = 5.0;       // Arduino besleme voltajı
const float R_fixed    = 10000;     // Pull-down direnci (10kΩ)
const float sensorArea = 4.06;      // FSR sensör etkin alanı (in²)
const float noktaArea  = 0.257;     // Nokta sensör etkin alanı (in²)
const float A          = 153.1;
const float B          = -0.69;

// ADXL345 nesnelerinin oluşturulması
ADXL345_WE myAcc1 = ADXL345_WE(CS_PIN1, spi);
ADXL345_WE myAcc2 = ADXL345_WE(CS_PIN2, spi);
ADXL345_WE myAcc3 = ADXL345_WE(CS_PIN3, spi);
ADXL345_WE myAcc4 = ADXL345_WE(CS_PIN4, spi);
ADXL345_WE myAcc5 = ADXL345_WE(CS_PIN5, spi);
ADXL345_WE myAcc6 = ADXL345_WE(CS_PIN6, spi);
ADXL345_WE myAcc7 = ADXL345_WE(CS_PIN7, spi);

// Vektör hesaplama fonksiyonları
float magnitude(xyzFloat v) {
  return sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}
float dotProduct(xyzFloat v1, xyzFloat v2) {
  return (v1.x * v2.x + v1.y * v2.y + v1.z * v2.z);
}
float calculateAngle(xyzFloat v1, xyzFloat v2) {
  float magV1 = magnitude(v1);
  float magV2 = magnitude(v2);
  float dotProd = dotProduct(v1, v2);
  float angle = acos(dotProd / (magV1 * magV2)); // Radyan cinsinden
  return angle * (180.0 / M_PI);                // Dereceye çevirme
}

void setup() {
  // USB seri monitör (debug)
  Serial.begin(115200);
  // Mega ile ESP8266 arasındaki iletişim için Serial3 (DIP switch ile ESP'ye bağlı)
  Serial2.begin(115200);

  Serial.println("ADXL345 Sensor Setup");
  delay(100);

  // ADXL345 sensörlerini başlatma
  if (!myAcc1.init()) {
    Serial.println("ADXL345-1 not connected!");
  } else {
    Serial.println("ADXL345-1 connected.");
    myAcc1.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc1.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc2.init()) {
    Serial.println("ADXL345-2 not connected!");
  } else {
    Serial.println("ADXL345-2 connected.");
    myAcc2.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc2.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc3.init()) {
    Serial.println("ADXL345-3 not connected!");
  } else {
    Serial.println("ADXL345-3 connected.");
    myAcc3.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc3.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc4.init()) {
    Serial.println("ADXL345-4 not connected!");
  } else {
    Serial.println("ADXL345-4 connected.");
    myAcc4.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc4.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc5.init()) {
    Serial.println("ADXL345-5 not connected!");
  } else {
    Serial.println("ADXL345-5 connected.");
    myAcc5.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc5.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc6.init()) {
    Serial.println("ADXL345-6 not connected!");
  } else {
    Serial.println("ADXL345-6 connected.");
    myAcc6.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc6.setRange(ADXL345_RANGE_4G);
  }
  if (!myAcc7.init()) {
    Serial.println("ADXL345-7 not connected!");
  } else {
    Serial.println("ADXL345-7 connected.");
    myAcc7.setDataRate(ADXL345_DATA_RATE_12_5);
    myAcc7.setRange(ADXL345_RANGE_4G);
  }
}

void loop() {
  StaticJsonDocument<2048> jsonDoc;

  // FSR sensör verileri (5 adet)
  JsonArray fsrSensors = jsonDoc.createNestedArray("fsr_sensors");
  for (int i = 0; i < 5; i++) {
    int adcValue = analogRead(sensorPins[i]);
    float Vout = (adcValue / 1023.0) * Vcc;
    float Rfsr = (Vcc * R_fixed / Vout) - R_fixed;
    float force_g = A * pow(Rfsr, B) * 1000;
    float force_N = force_g * 0.0098;
    float force_lb = force_g * 0.00220462;
    float psi = force_lb / sensorArea;
    JsonObject sensorObj = fsrSensors.createNestedObject();
    //sensorObj["sensor_type"] = "FSR";
    //sensorObj["sensor_pin"] = sensorPins[i];
    //sensorObj["adc"] = adcValue;
    //sensorObj["voltage"] = Vout;
    //sensorObj["resistance"] = Rfsr;
    //sensorObj["force_g"] = force_g;
    //sensorObj["force_N"] = force_N;
    sensorObj["psi" + String(i+1)] = psi;    //fsr sensörü print
  }

  // Nokta sensör verileri (9 adet)
  JsonArray noktaSensors = jsonDoc.createNestedArray("nokta_sensors");
  for (int i = 0; i < 9; i++) {
    int adcValue = analogRead(noktaPins[i]);
    float Vout = (adcValue / 1023.0) * Vcc;
    float Rfsr = (Vcc * R_fixed / Vout) - R_fixed;
    float force_g = A * pow(Rfsr, B) * 1000;
    float force_N = force_g * 0.0098;
    float force_lb = force_g * 0.00220462;
    float psi = force_lb / noktaArea;
    JsonObject sensorObj = noktaSensors.createNestedObject();
    //sensorObj["sensor_type"] = "Nokta";
    //sensorObj["sensor_pin"] = noktaPins[i];
    //sensorObj["adc"] = adcValue;
    //sensorObj["voltage"] = Vout;
    //sensorObj["resistance"] = Rfsr;
    //sensorObj["force_g"] = force_g;
    //sensorObj["force_N"] = force_N;
    sensorObj["psi"+ String(i+1)] = psi;
  }


// ADXL345 verileri (7 adet)
ADXL345_WE* adxlArray[7] = { &myAcc1, &myAcc2, &myAcc3, &myAcc4, &myAcc5, &myAcc6, &myAcc7 };

xyzFloat gValues[7];  // Sensörlerden gelen verileri saklamak için dizi


double dizi[6];
// Tüm sensörlerden değerleri al
for (int i = 0; i < 7; i++) {
    adxlArray[i]->getGValues(&gValues[i]);  
      
}

JsonArray dizis = jsonDoc.createNestedArray("dizis");  // JSON içinde açılar için dizi oluştur
// Sensör 1 ile diğer sensörler arasındaki açıları hesapla
for (int i = 0; i < 6; i++) {
    JsonObject sensorObj = dizis.createNestedObject();  // Yeni bir JSON nesnesi oluştur    
    dizi[i]= calculateAngle(gValues[0], gValues[i + 1]);
    double angleA = dizi[i];
    sensorObj["aci1_"+String(i+2)] = angleA;
}


 
  //jsonDoc["timestamp"] = millis();

  String output;
  serializeJson(jsonDoc, output);

  // Mega verisini ESP8266’ya (Serial3 üzerinden) gönderiyoruz.
  Serial2.println(output);
  // Debug için USB üzerinden seri monitöre yazdırıyoruz.
  Serial.println(output);

delay(1000);
}
