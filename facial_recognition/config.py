"""
config.py - Central configuration for the Facial Recognition System.
Values are loaded from the project-root .env file (if present),
falling back to the defaults listed here.
"""

import os
from pathlib import Path

# Load .env from the project root (one level above this file)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass   # python-dotenv not installed — use os.environ / defaults

# ─────────────────────────────────────────────
#  CAMERA CONFIGURATION
# ─────────────────────────────────────────────

# Camera source options:
#   - 0, 1, 2 ...  → PC webcam index (0 = default webcam)
#   - "http://192.168.x.x/stream" → ESP32-CAM MJPEG stream URL

_cam_src = os.environ.get("CAMERA_SOURCE", "0")
CAMERA_SOURCE = int(_cam_src) if _cam_src.isdigit() else _cam_src

FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

# ─────────────────────────────────────────────
#  RECOGNITION CONFIGURATION
# ─────────────────────────────────────────────

RECOGNITION_THRESHOLD = 0.5
DETECTION_MODEL       = "hog"
UPSAMPLE_TIMES        = 1

# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
ENCODINGS_FILE  = os.path.join(BASE_DIR, "data", "encodings.pkl")
LOG_FILE        = os.path.join(BASE_DIR, "data", "recognition_log.json")

# ─────────────────────────────────────────────
#  WEB SERVER
# ─────────────────────────────────────────────

HOST       = "0.0.0.0"
PORT       = int(os.environ.get("FACIAL_PORT",   5000))
DEBUG      = os.environ.get("FLASK_DEBUG", "True").lower() != "false"
SECRET_KEY = os.environ.get("FACIAL_SECRET_KEY", "fr-system-secret-2024")

# ─────────────────────────────────────────────
#  ESP32-CAM SPECIFIC
# ─────────────────────────────────────────────

ESP32_IP          = os.environ.get("ESP32_CAM_IP", "192.168.1.100")
ESP32_PORT        = 80
ESP32_STREAM_PATH = "/stream"
ESP32_STILL_PATH  = "/capture"

ESP32_STREAM_URL = f"http://{ESP32_IP}:{ESP32_PORT}{ESP32_STREAM_PATH}"
ESP32_STILL_URL  = f"http://{ESP32_IP}:{ESP32_PORT}{ESP32_STILL_PATH}"
