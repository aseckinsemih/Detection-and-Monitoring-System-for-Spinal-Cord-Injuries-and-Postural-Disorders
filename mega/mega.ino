/*******************************************************
 * Mega Code - Streams sensor data in JSON format
 *
 * PHYSICAL -> LOGICAL POSITION MAP
 * ─────────────────────────────────────────────────
 *  POS 0 : O_L  (Left Shoulder)     -> ACC1   CS=4
 *  POS 1 : O_R  (Right Shoulder)    -> ACC2   CS=6
 *  POS 2 : Upper back (neck base)   -> S_4    CS=3   (was ACC6)
 *  POS 3 : Mid back                 -> S_5    CS=5   (was ACC7)
 *  POS 4 : Lower back               -> S_1    CS=2   (was ACC3)
 *
 *  BYPASSED: S_2 (CS=9) and S_3 (CS=7) - hardware faulty, unused
 *******************************************************/
#include <ADXL345_WE.h>
#include <SPI.h>
#include <math.h>
#include <ArduinoJson.h>

// --- Chip Select Pins ---
#define CS_OL  4   // POS 0 - Left Shoulder
#define CS_OR  6   // POS 1 - Right Shoulder
#define CS_TOP 3   // POS 2 - Upper back (S_4)
#define CS_MID 5   // POS 3 - Mid back    (S_5)
#define CS_LOW 2   // POS 4 - Lower back  (S_1)

#define ACTIVE_COUNT 5

// --- Sensor verification parameters ---
// The DEVID read is unreliable on some CS lines, so a sensor is considered
// "verified" only when it returns a physically plausible gravity vector.
// A healthy ADXL345 at rest reads a magnitude of ~1g.
#define VERIFY_MIN_G        0.5    // minimum acceptable gravity magnitude
#define VERIFY_MAX_G        1.5    // maximum acceptable gravity magnitude
#define VERIFY_MAX_ATTEMPTS 50     // max verification rounds (~5s) before aborting

bool spi = true;

// FSR strip and point sensors
const int sensorPins[] = {A0, A1, A2, A3, A6};
const int noktaPins[]  = {A4, A5, A10, A7, A8, A9, A11, A12, A13};

// Constants
const float Vcc        = 5.0;
const float R_fixed    = 10000;
const float sensorArea = 4.06;
const float noktaArea  = 0.257;
const float A_coef     = 153.1;
const float B_coef     = -0.69;

// --- ADXL345 objects (active sensors only) ---
ADXL345_WE accOL  = ADXL345_WE(CS_OL,  spi);   // POS 0
ADXL345_WE accOR  = ADXL345_WE(CS_OR,  spi);   // POS 1
ADXL345_WE accTOP = ADXL345_WE(CS_TOP, spi);   // POS 2 - S_4
ADXL345_WE accMID = ADXL345_WE(CS_MID, spi);   // POS 3 - S_5
ADXL345_WE accLOW = ADXL345_WE(CS_LOW, spi);   // POS 4 - S_1

ADXL345_WE* spine[ACTIVE_COUNT] = { &accOL, &accOR, &accTOP, &accMID, &accLOW };
const int   csPin[ACTIVE_COUNT] = { CS_OL,  CS_OR,  CS_TOP,  CS_MID,  CS_LOW  };

// Per-sensor verification state. A sensor is marked ready only after it
// returns a plausible gravity reading, not based on the unreliable DEVID check.
bool sensorReady[ACTIVE_COUNT] = { false, false, false, false, false };
const char* posName[ACTIVE_COUNT] = {
  "O_L",        // 0
  "O_R",        // 1
  "S4_top",     // 2 - upper back
  "S5_mid",     // 3 - mid back
  "S1_low"      // 4 - lower back
};

// --- Vector helpers ---
float magnitude(xyzFloat v) {
  return sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}
float dotProduct(xyzFloat v1, xyzFloat v2) {
  return v1.x * v2.x + v1.y * v2.y + v1.z * v2.z;
}
float calculateAngle(xyzFloat v1, xyzFloat v2) {
  float m1 = magnitude(v1), m2 = magnitude(v2);
  if (m1 == 0 || m2 == 0) return 0.0;
  float cosA = dotProduct(v1, v2) / (m1 * m2);
  if (cosA >  1.0) cosA =  1.0;   // clamp against float rounding -> NaN
  if (cosA < -1.0) cosA = -1.0;
  return acos(cosA) * (180.0 / M_PI);
}

// Configure a single sensor. The init() return value is ignored because the
// DEVID check is unreliable; the registers still get written, so the sensor
// becomes physically operational regardless.
void configureSensor(int i) {
  spine[i]->init();                           // write registers
  spine[i]->setDataRate(ADXL345_DATA_RATE_12_5);
  spine[i]->setRange(ADXL345_RANGE_4G);
  spine[i]->setMeasureMode(true);             // force measurement mode on
}

// Verify a sensor by reading its gravity vector. Returns true only if the
// magnitude is physically plausible (rejects dead / zero / garbage readings).
bool verifySensor(int i) {
  xyzFloat v;
  spine[i]->getGValues(&v);
  float m = magnitude(v);
  if (isnan(m) || isinf(m)) return false;
  return (m >= VERIFY_MIN_G && m <= VERIFY_MAX_G);
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200);

  // CRITICAL: drive all CS pins HIGH before SPI.begin() to prevent bus
  // contention. The unused S_2 (CS=9) and S_3 (CS=7) are also pulled HIGH
  // so they do not float.
  const int allCsPins[7] = { 4, 6, 2, 9, 7, 3, 5 };
  for (int i = 0; i < 7; i++) {
    pinMode(allCsPins[i], OUTPUT);
    digitalWrite(allCsPins[i], HIGH);
  }
  SPI.begin();
  delay(100);

  Serial.println(F("=== ADXL345 Setup (5 sensors) ==="));

  // Initial configuration pass
  for (int i = 0; i < ACTIVE_COUNT; i++) {
    configureSensor(i);
  }

  // --- Verification gate ---
  // Do NOT start streaming until every active sensor returns a valid gravity
  // reading. Sensors that fail are reconfigured and retried each round.
  int attempt = 0;
  int verifiedCount = 0;
  while (verifiedCount < ACTIVE_COUNT && attempt < VERIFY_MAX_ATTEMPTS) {
    attempt++;
    verifiedCount = 0;
    for (int i = 0; i < ACTIVE_COUNT; i++) {
      if (!sensorReady[i]) {
        if (verifySensor(i)) {
          sensorReady[i] = true;
          Serial.print(F("VERIFIED: POS "));
          Serial.print(i);
          Serial.print(F(" - "));
          Serial.println(posName[i]);
        } else {
          configureSensor(i);   // reconfigure and retry next round
        }
      }
      if (sensorReady[i]) verifiedCount++;
    }
    delay(100);
  }

  // Final status report
  for (int i = 0; i < ACTIVE_COUNT; i++) {
    Serial.print(F("POS ")); Serial.print(i);
    Serial.print(F(" - ")); Serial.print(posName[i]);
    Serial.print(F(" (CS=")); Serial.print(csPin[i]); Serial.print(F(") "));
    Serial.println(sensorReady[i] ? F("... READY") : F("... FAILED"));
  }

  Serial.print(F("Verified sensors: "));
  Serial.print(verifiedCount); Serial.print(F("/"));
  Serial.println(ACTIVE_COUNT);

  // Streaming starts ONLY when all sensors are confirmed. If any failed to
  // verify within the timeout, halt instead of streaming unreliable data.
  if (verifiedCount < ACTIVE_COUNT) {
    Serial.println(F("ABORT: not all sensors verified. Streaming will NOT start."));
    Serial.println(F("Check wiring/power for the FAILED sensors above, then reset."));
    Serial.println(F("======================================"));
    while (true) { /* halt */ }
  }

  Serial.println(F("All sensors verified. Starting data stream."));
  Serial.println(F("======================================"));
}

void loop() {
  StaticJsonDocument<2048> jsonDoc;

  // ─────────── FSR strips (5 sensors) ───────────
  JsonArray fsrSensors = jsonDoc.createNestedArray("fsr_sensors");
  for (int i = 0; i < 5; i++) {
    int adcValue = analogRead(sensorPins[i]);
    float Vout = (adcValue / 1023.0) * Vcc;
    float psi = 0.0;
    if (Vout > 0.01) {
      float Rfsr = (Vcc * R_fixed / Vout) - R_fixed;
      if (Rfsr > 0) {
        float force_g  = A_coef * pow(Rfsr, B_coef) * 1000;
        float force_lb = force_g * 0.00220462;
        psi = force_lb / sensorArea;
      }
    }
    JsonObject obj = fsrSensors.createNestedObject();
    obj["psi" + String(i + 1)] = psi;
  }

  // ─────────── Point sensors (9 sensors) ───────────
  JsonArray noktaSensors = jsonDoc.createNestedArray("nokta_sensors");
  for (int i = 0; i < 9; i++) {
    int adcValue = analogRead(noktaPins[i]);
    float Vout = (adcValue / 1023.0) * Vcc;
    float psi = 0.0;
    if (Vout > 0.01) {
      float Rfsr = (Vcc * R_fixed / Vout) - R_fixed;
      if (Rfsr > 0) {
        float force_g  = A_coef * pow(Rfsr, B_coef) * 1000;
        float force_lb = force_g * 0.00220462;
        psi = force_lb / noktaArea;
      }
    }
    JsonObject obj = noktaSensors.createNestedObject();
    obj["psi" + String(i + 1)] = psi;
  }

  // ─────────── ADXL345 raw g values (5 sensors, POS 0..4) ───────────
  xyzFloat gValues[ACTIVE_COUNT];
  for (int i = 0; i < ACTIVE_COUNT; i++) {
    spine[i]->getGValues(&gValues[i]);
  }

  // ─────────── Angle array: referenced to POS 0 (Left Shoulder) ───────────
  // Output order from neck downward: O_R -> S_4 -> S_5 -> S_1
  JsonArray dizis = jsonDoc.createNestedArray("dizis");
  for (int i = 1; i < ACTIVE_COUNT; i++) {
    JsonObject obj = dizis.createNestedObject();
    float ang = calculateAngle(gValues[0], gValues[i]);
    // Position-based key names: "aci_OL_<target>"
    String key = String("aci_OL_") + posName[i];
    obj[key] = ang;
  }

  // ─────────── Per-sensor raw pitch/roll angles (for spine curve) ───────────
  // PyQt needs pitch and roll to draw the spinal curve
  JsonArray pitchRoll = jsonDoc.createNestedArray("pitch_roll");
  for (int i = 0; i < ACTIVE_COUNT; i++) {
    JsonObject obj = pitchRoll.createNestedObject();
    float p = atan2(gValues[i].y, gValues[i].z) * (180.0 / M_PI);
    float r = atan2(-gValues[i].x,
                    sqrt(gValues[i].y * gValues[i].y + gValues[i].z * gValues[i].z))
              * (180.0 / M_PI);
    obj["pos"]   = posName[i];
    obj["pitch"] = p;
    obj["roll"]  = r;
  }

  // ─────────── Send JSON ───────────
  String output;
  serializeJson(jsonDoc, output);

  Serial2.println(output);
  Serial.println(output);

  delay(50);
}
