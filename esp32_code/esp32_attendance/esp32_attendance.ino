/*
 * esp32_attendance.ino
 * =====================================================================
 * ESP32-S3 Attendance Kiosk — Face + Fingerprint Dual Verification
 *
 * HARDWARE REQUIRED:
 *   - ESP32-S3 development board
 *   - TFT display (any supported by TFT_eSPI — configure User_Setup.h)
 *   - R307 / R503 / AS608 fingerprint sensor (UART, 3.3V)
 *
 * ARDUINO LIBRARY MANAGER — install these before compiling:
 *   1. TFT_eSPI          by Bodmer
 *   2. Adafruit Fingerprint Sensor Library  by Adafruit
 *   3. ArduinoJson       by Benoit Blanchon   (v6 or v7)
 *
 * BEFORE UPLOADING:
 *   1. Edit config.h  — set WiFi name, password, and server IP
 *   2. Edit TFT_eSPI/User_Setup.h to match your TFT display model and pins
 *   3. Flash the board using Arduino IDE with "ESP32S3 Dev Module" board
 * =====================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <Adafruit_Fingerprint.h>
#include "config.h"

// ── Hardware objects ──────────────────────────────────────────────
TFT_eSPI        tft;
HardwareSerial  fpSerial(2);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&fpSerial);

// ── State machine ─────────────────────────────────────────────────
enum KioskState {
  S_CONNECTING,
  S_IDLE,
  S_FACE_DETECTED,
  S_NOT_REGISTERED,
  S_FP_WAIT,
  S_FP_VERIFIED,
  S_FP_FAILED,
  S_TIMETABLE
};

KioskState state     = S_CONNECTING;
KioskState lastState = (KioskState)-1;  // forces first render

// Recognition info received from server
String recognizedName = "";
float  recognizedConf = 0.0f;

// Timing
unsigned long stateEnteredAt  = 0;
unsigned long lastPollAt      = 0;
unsigned long lastFpRedrawAt  = 0;

// Timetable data returned after attendance is marked
struct ClassEntry { String period, time, subject, teacher; };
ClassEntry classes[10];
int    classCount = 0;
String classDay   = "";

// ── Utility: set new state ─────────────────────────────────────────
void setState(KioskState s) {
  state          = s;
  stateEnteredAt = millis();
}

unsigned long timeInState() {
  return millis() - stateEnteredAt;
}

// ══════════════════════════════════════════════════════════════════
// SCREEN RENDERERS
// ══════════════════════════════════════════════════════════════════

int W, H;   // screen dimensions, set in setup()

void centered(const String& txt, int y, uint16_t color, uint8_t font = 2) {
  tft.setTextColor(color, C_BG);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(txt, W / 2, y, font);
  tft.setTextDatum(TL_DATUM);
}

void topBar(const char* title, uint16_t color) {
  tft.fillRect(0, 0, W, 44, color);
  tft.setTextColor(C_WHITE, color);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(title, W / 2, 22, 2);
  tft.setTextDatum(TL_DATUM);
}

// ── Connecting screen ─────────────────────────────────────────────
void screenConnecting() {
  tft.fillScreen(C_BG);
  tft.fillRect(0, 0, W, 4, C_ACCENT);
  centered("Connecting to WiFi...", H / 2 - 16, C_GRAY, 2);
  centered(WIFI_SSID, H / 2 + 8, C_WHITE, 2);
}

// ── Idle screen ───────────────────────────────────────────────────
void screenIdle() {
  tft.fillScreen(C_BG);

  // Top accent strip
  tft.fillRect(0, 0, W, 5, C_ACCENT);

  // Camera icon circle
  int cx = W / 2, cy = H / 2 - 20;
  tft.fillCircle(cx, cy, 44, C_CARD);
  tft.drawCircle(cx, cy, 44, C_ACCENT);
  tft.drawCircle(cx, cy, 42, C_ACCENT);
  // Lens
  tft.fillCircle(cx, cy, 20, C_BG);
  tft.drawCircle(cx, cy, 20, C_ACCENT);
  tft.fillCircle(cx, cy, 8, C_ACCENT);

  centered("Please stand in front", cy + 65, C_GRAY, 2);
  centered("of the camera", cy + 85, C_WHITE, 2);

  // Bottom dots
  for (int i = -2; i <= 2; i++) {
    tft.fillCircle(cx + i * 14, H - 22, 4, i == 0 ? C_ACCENT : C_DGRAY);
  }
}

// ── Face detected screen ──────────────────────────────────────────
void screenFaceDetected() {
  tft.fillScreen(C_BG);
  topBar("FACE RECOGNIZED", C_ACCENT);

  // Name card
  tft.fillRoundRect(10, 54, W - 20, 52, 8, C_CARD);
  tft.drawRoundRect(10, 54, W - 20, 52, 8, C_ACCENT);
  tft.setTextColor(C_ACCENT, C_CARD);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(recognizedName, W / 2, 80, 4);
  tft.setTextDatum(TL_DATUM);

  String confStr = String((int)(recognizedConf * 100)) + "% confidence";
  centered(confStr, 116, C_GRAY, 2);

  tft.drawFastHLine(20, 132, W - 40, C_DGRAY);

  centered("Place your finger", 150, C_WHITE, 2);
  centered("on the scanner below", 170, C_WHITE, 2);

  // Fingerprint icon
  int fx = W / 2, fy = H - 50;
  tft.drawCircle(fx, fy, 28, C_GREEN);
  tft.drawCircle(fx, fy, 20, C_GREEN);
  tft.drawCircle(fx, fy, 12, C_GREEN);
  tft.fillCircle(fx, fy, 5, C_GREEN);
}

// ── Not registered screen ─────────────────────────────────────────
void screenNotRegistered() {
  tft.fillScreen(C_BG);
  topBar("NOT REGISTERED", C_RED);

  int cx = W / 2, cy = H / 2 - 10;
  tft.fillCircle(cx, cy, 42, 0x2000);
  tft.drawCircle(cx, cy, 42, C_RED);
  tft.setTextColor(C_RED, 0x2000);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("!", cx, cy, 6);
  tft.setTextDatum(TL_DATUM);

  centered("Face not found", cy + 58, C_GRAY, 2);
  centered("in the database", cy + 78, C_WHITE, 2);
  centered("Contact administrator", cy + 100, C_AMBER, 2);
}

// ── Fingerprint wait screen ───────────────────────────────────────
void screenFpWait(int secondsLeft) {
  // Only redraw the timer number — avoid full-screen flicker
  static int lastSec = -1;
  if (secondsLeft == lastSec) return;
  lastSec = secondsLeft;

  if (lastState != S_FP_WAIT) {
    // First render: draw everything
    tft.fillScreen(C_BG);
    topBar("SCAN FINGERPRINT", C_AMBER);
    centered(recognizedName, 58, C_ACCENT, 2);
    centered("Keep your finger still", 168, C_WHITE, 2);
    centered("on the scanner", 188, C_GRAY, 2);
  }

  // Timer circle (redraw only timer region)
  int cx = W / 2, cy = 118;
  tft.fillCircle(cx, cy, 36, C_CARD);
  tft.drawCircle(cx, cy, 36, C_AMBER);
  tft.setTextColor(C_AMBER, C_CARD);
  tft.setTextDatum(MC_DATUM);
  tft.drawString(String(secondsLeft), cx, cy, 4);
  tft.setTextDatum(TL_DATUM);
}

// ── Verified screen ───────────────────────────────────────────────
void screenVerified() {
  tft.fillScreen(C_BG);
  topBar("ATTENDANCE MARKED", C_GREEN);

  int cx = W / 2, cy = H / 2 - 26;
  tft.fillCircle(cx, cy, 44, 0x0460);
  tft.drawCircle(cx, cy, 44, C_GREEN);
  tft.setTextColor(C_GREEN, 0x0460);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("OK", cx, cy, 4);
  tft.setTextDatum(TL_DATUM);

  centered(recognizedName, cy + 60, C_WHITE, 4);
  centered("Verified & Recorded!", cy + 88, C_GREEN, 2);
}

// ── Fingerprint failed screen ─────────────────────────────────────
void screenFpFailed() {
  tft.fillScreen(C_BG);
  topBar("VERIFICATION FAILED", C_RED);

  centered("Fingerprint", H / 2 - 30, C_RED, 4);
  centered("not matched", H / 2,      C_RED, 4);
  centered("Please try again", H / 2 + 46, C_GRAY, 2);
  centered("or contact admin",  H / 2 + 66, C_AMBER, 2);
}

// ── Timetable screen ──────────────────────────────────────────────
void screenTimetable() {
  tft.fillScreen(C_BG);

  // Header
  tft.fillRect(0, 0, W, 44, 0x0020);
  tft.setTextColor(C_GRAY, 0x0020);
  tft.drawString("Today  " + classDay, 10, 8, 2);
  tft.setTextColor(C_ACCENT, 0x0020);
  String nameShort = recognizedName.length() > 18
                      ? recognizedName.substring(0, 16) + ".."
                      : recognizedName;
  tft.drawString(nameShort, 10, 26, 2);

  if (classCount == 0) {
    centered("No classes today!", H / 2, C_GRAY, 4);
    return;
  }

  int y = 50;
  int rowH = min(34, (H - 54) / classCount);

  for (int i = 0; i < classCount && y < H - 6; i++) {
    uint16_t bg = (i % 2 == 0) ? C_CARD : 0x0841;
    tft.fillRect(0, y, W, rowH - 1, bg);

    // Period pill
    tft.fillRect(4, y + 4, 26, rowH - 10, C_ACCENT);
    tft.setTextColor(C_WHITE, C_ACCENT);
    tft.setTextDatum(MC_DATUM);
    tft.drawString(classes[i].period, 17, y + rowH / 2, 1);
    tft.setTextDatum(TL_DATUM);

    // Time
    tft.setTextColor(C_GRAY, bg);
    tft.drawString(classes[i].time, 34, y + 4, 1);

    // Subject (truncate if needed)
    String sub = classes[i].subject;
    if (sub.length() > 17) sub = sub.substring(0, 15) + "..";
    tft.setTextColor(C_WHITE, bg);
    tft.drawString(sub, 34, y + 14, 2);

    y += rowH;
  }
}

// ── Master render dispatcher ──────────────────────────────────────
void render() {
  if (state == S_FP_WAIT) {
    int secLeft = max(0, (int)((FP_TIMEOUT_MS - (long)timeInState()) / 1000));
    screenFpWait(secLeft);
    lastState = S_FP_WAIT;
    return;
  }
  if (state == lastState) return;   // no change — skip
  lastState = state;

  switch (state) {
    case S_CONNECTING:    screenConnecting();    break;
    case S_IDLE:          screenIdle();          break;
    case S_FACE_DETECTED: screenFaceDetected();  break;
    case S_NOT_REGISTERED:screenNotRegistered(); break;
    case S_FP_VERIFIED:   screenVerified();      break;
    case S_FP_FAILED:     screenFpFailed();      break;
    case S_TIMETABLE:     screenTimetable();     break;
    default: break;
  }
}

// ══════════════════════════════════════════════════════════════════
// NETWORKING
// ══════════════════════════════════════════════════════════════════

String buildURL(const String& path) {
  return "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + path;
}

String httpGET(const String& path) {
  if (WiFi.status() != WL_CONNECTED) return "";
  HTTPClient http;
  http.begin(buildURL(path));
  http.setTimeout(3000);
  int code = http.GET();
  String body = (code == 200) ? http.getString() : "";
  http.end();
  return body;
}

String httpPOST(const String& path, const String& json) {
  if (WiFi.status() != WL_CONNECTED) return "";
  HTTPClient http;
  http.begin(buildURL(path));
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);
  int code = http.POST(json);
  String body = (code > 0) ? http.getString() : "";
  http.end();
  return body;
}

// ── Poll server for recognition state ────────────────────────────
void pollServer() {
  String body = httpGET("/api/esp32/poll");
  if (body.isEmpty()) return;

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, body)) return;

  const char* sv = doc["state"] | "idle";

  if (strcmp(sv, "face_detected") == 0) {
    // Only update if we are idle (don't interrupt mid-scan)
    if (state == S_IDLE || state == S_NOT_REGISTERED) {
      recognizedName = doc["name"] | "Unknown";
      recognizedConf = doc["confidence"] | 0.0f;
      setState(S_FACE_DETECTED);
    }
  } else if (strcmp(sv, "not_registered") == 0) {
    if (state == S_IDLE) {
      setState(S_NOT_REGISTERED);
    }
  } else {
    // idle
    if (state == S_NOT_REGISTERED && timeInState() > NOTFOUND_SHOW_MS) {
      setState(S_IDLE);
    }
  }
}

// ── Mark attendance & parse timetable ────────────────────────────
void markAttendance(int fpId) {
  StaticJsonDocument<128> req;
  req["name"]           = recognizedName;
  req["fingerprint_id"] = fpId;
  String reqStr;
  serializeJson(req, reqStr);

  String resp = httpPOST("/api/attendance/mark", reqStr);
  if (resp.isEmpty()) return;

  // Parse timetable from response
  DynamicJsonDocument doc(4096);
  if (deserializeJson(doc, resp)) return;

  classCount = 0;
  classDay   = doc["timetable"]["day"] | "";
  JsonArray arr = doc["timetable"]["classes"];
  for (JsonObject c : arr) {
    if (classCount >= 10) break;
    classes[classCount].period  = c["period"]  | "";
    classes[classCount].time    = c["time"]    | "";
    classes[classCount].subject = c["subject"] | "";
    classes[classCount].teacher = c["teacher"] | "";
    classCount++;
  }
}

// ── Reset server state ────────────────────────────────────────────
void resetServer() {
  httpPOST("/api/esp32/reset", "{}");
}

// ══════════════════════════════════════════════════════════════════
// FINGERPRINT SCANNING
// ══════════════════════════════════════════════════════════════════

//  Returns:  >0  = fingerprint ID matched
//            -1  = timeout
//            -2  = image captured but no DB match
int scanFingerprint() {
  while (timeInState() < FP_TIMEOUT_MS) {
    render();   // keep timer updated

    int p = finger.getImage();
    if (p == FINGERPRINT_NOFINGER) { delay(80); continue; }
    if (p != FINGERPRINT_OK)       { delay(80); continue; }

    // Image captured
    p = finger.image2Tz();
    if (p != FINGERPRINT_OK) continue;

    p = finger.fingerSearch();
    if (p == FINGERPRINT_OK)       return finger.fingerID;
    else                           return -2;
  }
  return -1;   // timeout
}

// ══════════════════════════════════════════════════════════════════
// WIFI
// ══════════════════════════════════════════════════════════════════

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 40) {
    delay(500);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi OK: " + WiFi.localIP().toString());
  } else {
    Serial.println("WiFi FAILED");
  }
}

// ══════════════════════════════════════════════════════════════════
// SETUP & LOOP
// ══════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);

  // Init TFT
  tft.init();
  tft.setRotation(0);
  W = tft.width();
  H = tft.height();
  tft.fillScreen(C_BG);

  setState(S_CONNECTING);
  render();

  // Init fingerprint sensor
  fpSerial.begin(FP_BAUD, SERIAL_8N1, FP_RX_PIN, FP_TX_PIN);
  finger.begin(FP_BAUD);
  if (finger.verifyPassword()) {
    Serial.println("Fingerprint sensor ready");
  } else {
    Serial.println("WARNING: fingerprint sensor not found — check wiring");
  }

  // Connect WiFi
  connectWiFi();
  setState(S_IDLE);
  render();
}

void loop() {
  // ── Reconnect WiFi if dropped ──────────────────────────────────
  if (WiFi.status() != WL_CONNECTED) {
    setState(S_CONNECTING);
    render();
    connectWiFi();
    setState(S_IDLE);
    return;
  }

  // ── IDLE / NOT_REGISTERED — poll server ───────────────────────
  if ((state == S_IDLE || state == S_NOT_REGISTERED) &&
      millis() - lastPollAt >= POLL_INTERVAL_MS) {
    lastPollAt = millis();
    pollServer();
  }

  // ── Auto-dismiss NOT_REGISTERED after timeout ─────────────────
  if (state == S_NOT_REGISTERED && timeInState() > NOTFOUND_SHOW_MS) {
    setState(S_IDLE);
  }

  // ── FACE_DETECTED — brief pause then move to fingerprint ──────
  if (state == S_FACE_DETECTED && timeInState() > 1800) {
    setState(S_FP_WAIT);
    lastState = (KioskState)-1;   // force full screen redraw
  }

  // ── FP_WAIT — run fingerprint scan ────────────────────────────
  if (state == S_FP_WAIT) {
    int result = scanFingerprint();

    if (result > 0) {
      // ✓ Match found
      setState(S_FP_VERIFIED);
      lastState = (KioskState)-1;
      render();
      markAttendance(result);
      delay(VERIFIED_SHOW_MS);

      if (classCount > 0) {
        setState(S_TIMETABLE);
        lastState = (KioskState)-1;
        render();
        delay(TIMETABLE_SHOW_MS);
      }

    } else if (result == -2) {
      // ✗ Image captured but not in DB
      setState(S_FP_FAILED);
      lastState = (KioskState)-1;
      render();
      resetServer();
      delay(3000);

    } else {
      // Timeout
      resetServer();
    }

    setState(S_IDLE);
    lastState = (KioskState)-1;
    return;
  }

  render();
  delay(40);
}
