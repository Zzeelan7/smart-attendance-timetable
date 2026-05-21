// ================================================================
// config.h — Configuration for ESP32-S3 Attendance Kiosk
// Edit ONLY the values in this file to match your setup.
// ================================================================

#pragma once

// ── WiFi ─────────────────────────────────────────────────────────
#define WIFI_SSID     "YourWiFiName"        // << change this
#define WIFI_PASSWORD "YourWiFiPassword"    // << change this

// ── Server ───────────────────────────────────────────────────────
// IP of the PC running run_all.py (run `ipconfig` on that PC)
#define SERVER_IP     "192.168.1.100"       // << change this
#define SERVER_PORT   5000

// ── Fingerprint Scanner (UART) ───────────────────────────────────
// Wiring:  Sensor VCC → 3.3V,  Sensor GND → GND
//          Sensor TX  → ESP32 GPIO 16 (RX2)
//          Sensor RX  → ESP32 GPIO 17 (TX2)
#define FP_RX_PIN     16
#define FP_TX_PIN     17
#define FP_BAUD       57600

// ── Timing ───────────────────────────────────────────────────────
#define POLL_INTERVAL_MS   1000   // how often to poll server (ms)
#define FP_TIMEOUT_MS     15000   // fingerprint wait timeout (ms)
#define NOTFOUND_SHOW_MS   5000   // how long to show "not registered"
#define VERIFIED_SHOW_MS   2500   // how long to show "verified" screen
#define TIMETABLE_SHOW_MS  9000   // how long to show timetable

// ── TFT Colors (RGB565) ──────────────────────────────────────────
#define C_BG      0x0810   // dark navy background
#define C_CARD    0x10A2   // card background
#define C_ACCENT  0x4BBF   // blue accent
#define C_GREEN   0x07E0   // green
#define C_RED     0xF800   // red
#define C_AMBER   0xFD20   // amber / orange
#define C_WHITE   0xFFFF   // white
#define C_GRAY    0x7BEF   // light gray
#define C_DGRAY   0x39E7   // dark gray
