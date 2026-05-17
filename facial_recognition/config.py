"""
config.py - Central configuration for the Facial Recognition System.
Switch between PC Camera and ESP32-CAM by changing CAMERA_SOURCE.
"""

# ─────────────────────────────────────────────
#  CAMERA CONFIGURATION
# ─────────────────────────────────────────────

# Camera source options:
#   - 0, 1, 2 ...  → PC webcam index (0 = default webcam)
#   - "http://192.168.x.x/stream" → ESP32-CAM MJPEG stream URL
#   - "http://192.168.x.x:81/stream" → ESP32-CAM (alternative port)

CAMERA_SOURCE = 0  # <-- Change to your ESP32-CAM URL when ready

# Resolution to capture/process frames at
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

# ─────────────────────────────────────────────
#  RECOGNITION CONFIGURATION
# ─────────────────────────────────────────────

# Cosine distance threshold for face match (lower = stricter)
# Recommended range: 0.4 – 0.6
RECOGNITION_THRESHOLD = 0.5

# Face detection model: "hog" (CPU-fast) or "cnn" (GPU-accurate)
DETECTION_MODEL = "hog"

# Number of face detection upsamples (higher = detect smaller faces)
UPSAMPLE_TIMES = 1

# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────

import os
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
ENCODINGS_FILE  = os.path.join(BASE_DIR, "data", "encodings.pkl")
LOG_FILE        = os.path.join(BASE_DIR, "data", "recognition_log.json")

# ─────────────────────────────────────────────
#  WEB SERVER
# ─────────────────────────────────────────────

HOST = "0.0.0.0"
PORT = 5000
DEBUG = True
SECRET_KEY = "fr-system-secret-2024"

# ─────────────────────────────────────────────
#  ESP32-CAM SPECIFIC (for future use)
# ─────────────────────────────────────────────

ESP32_IP   = "192.168.1.100"     # Change to your ESP32-CAM IP
ESP32_PORT = 80
ESP32_STREAM_PATH = "/stream"
ESP32_STILL_PATH  = "/capture"   # Single frame capture endpoint

ESP32_STREAM_URL = f"http://{ESP32_IP}:{ESP32_PORT}{ESP32_STREAM_PATH}"
ESP32_STILL_URL  = f"http://{ESP32_IP}:{ESP32_PORT}{ESP32_STILL_PATH}"
