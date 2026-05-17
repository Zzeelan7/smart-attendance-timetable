"""
camera/esp32_camera.py
Handles video streaming from the ESP32-CAM module.

The ESP32-CAM runs its own web server that exposes:
  - /stream  → MJPEG continuous stream  (used here)
  - /capture → single JPEG snapshot

OpenCV's VideoCapture can read MJPEG streams directly from an HTTP URL,
so switching from PC camera to ESP32-CAM is a one-line config change.

ESP32-CAM Arduino sketch to use:
  - CameraWebServer example (included in Arduino ESP32 board package)
  - Set board to: AI-Thinker ESP32-CAM
  - Flash, note the IP from Serial Monitor, paste into config.py

Connection diagram:
  ESP32-CAM   →   FTDI Adapter (for flashing ONLY – not needed at runtime)
  5V/GND      →   VCC/GND
  U0RXD       →   TX
  U0TXD       →   RX
  IO0         →   GND  (flash mode – remove after flash)
"""

import cv2
import requests
import numpy as np
import logging
import time
import threading
from .base_camera import BaseCamera

logger = logging.getLogger(__name__)


class ESP32Camera(BaseCamera):
    """
    ESP32-CAM stream reader.

    Supports two read modes:
      1. MJPEG stream via OpenCV VideoCapture (preferred, low-latency)
      2. JPEG snapshot polling via HTTP requests (fallback)

    Usage:
        cam = ESP32Camera(stream_url="http://192.168.1.100/stream")
        cam.start()
        ok, frame = cam.read_frame()
        cam.release()
    """

    def __init__(self, stream_url: str,
                 width: int = 640, height: int = 480,
                 timeout: float = 5.0,
                 use_opencv_stream: bool = True):
        """
        Args:
            stream_url: Full URL to the MJPEG stream (e.g. http://IP/stream)
            width/height: Desired output resolution (resized locally)
            timeout: Connection timeout in seconds
            use_opencv_stream: If True, use cv2.VideoCapture; else use HTTP polling
        """
        self._stream_url        = stream_url
        self._width             = width
        self._height            = height
        self._timeout           = timeout
        self._use_opencv_stream = use_opencv_stream

        self._cap: cv2.VideoCapture | None = None
        self._opened = False

        # For HTTP polling fallback
        self._latest_frame: np.ndarray | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ─── BaseCamera interface ─────────────────────────────────────────────

    def start(self) -> bool:
        logger.info(f"Connecting to ESP32-CAM at: {self._stream_url}")

        # First check if the ESP32-CAM is reachable
        if not self._ping():
            logger.error("ESP32-CAM is not reachable. Check IP and WiFi.")
            return False

        if self._use_opencv_stream:
            return self._start_opencv_stream()
        else:
            return self._start_http_polling()

    def read_frame(self) -> tuple[bool, np.ndarray]:
        if not self._opened:
            return False, self._blank_frame()

        if self._use_opencv_stream and self._cap is not None:
            ok, frame = self._cap.read()
            if ok:
                frame = cv2.resize(frame, (self._width, self._height))
            return ok, frame
        else:
            # HTTP polling mode
            if self._latest_frame is not None:
                return True, self._latest_frame.copy()
            return False, self._blank_frame()

    def release(self):
        self._opened = False
        self._stop_event.set()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2.0)
        logger.info("ESP32-CAM connection released")

    def is_opened(self) -> bool:
        return self._opened

    @property
    def source_name(self) -> str:
        return f"ESP32-CAM ({self._stream_url})"

    # ─── Internal helpers ─────────────────────────────────────────────────

    def _ping(self) -> bool:
        """Check if the ESP32 web server responds."""
        try:
            base = self._stream_url.rsplit("/", 1)[0]
            r = requests.get(base, timeout=self._timeout)
            return r.status_code < 500
        except Exception:
            return False

    def _start_opencv_stream(self) -> bool:
        self._cap = cv2.VideoCapture(self._stream_url)
        # Give OpenCV time to buffer the first frame
        time.sleep(1.0)
        if self._cap.isOpened():
            self._opened = True
            logger.info("ESP32-CAM MJPEG stream opened via OpenCV")
            return True
        logger.warning("OpenCV stream failed. Falling back to HTTP polling.")
        return self._start_http_polling()

    def _start_http_polling(self) -> bool:
        """
        Fallback: continuously GET /capture (JPEG snapshot) in a background thread.
        Use this if MJPEG stream is unstable on your network.
        """
        # Convert /stream URL to /capture URL
        still_url = self._stream_url.replace("/stream", "/capture")
        self._stop_event.clear()

        def poll():
            while not self._stop_event.is_set():
                try:
                    resp = requests.get(still_url, timeout=self._timeout, stream=True)
                    arr = np.frombuffer(resp.content, np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        self._latest_frame = cv2.resize(frame, (self._width, self._height))
                except Exception as e:
                    logger.debug(f"Poll error: {e}")

        self._poll_thread = threading.Thread(target=poll, daemon=True)
        self._poll_thread.start()
        time.sleep(0.5)
        self._opened = True
        logger.info("ESP32-CAM HTTP polling started")
        return True

    def _blank_frame(self) -> np.ndarray:
        return np.zeros((self._height, self._width, 3), dtype=np.uint8)
