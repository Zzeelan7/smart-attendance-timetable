"""
camera/pc_camera.py
Handles local webcam capture using OpenCV.
Works with any USB/built-in webcam on Windows, Linux, or Mac.
"""

import sys
import cv2
import logging
import numpy as np
from .base_camera import BaseCamera

logger = logging.getLogger(__name__)


class PCCamera(BaseCamera):
    """
    PC / USB webcam camera source.
    Uses OpenCV's VideoCapture with an integer device index.

    Usage:
        cam = PCCamera(device_index=0)   # 0 = default webcam
        cam.start()
        ok, frame = cam.read_frame()
        cam.release()
    """

    def __init__(self, device_index: int = 0,
                 width: int = 640, height: int = 480):
        self._index  = device_index
        self._width  = width
        self._height = height
        self._cap: cv2.VideoCapture | None = None

    # ─── BaseCamera interface ─────────────────────────────────────────────

    def start(self) -> bool:
        is_windows = sys.platform.startswith("win")
        logger.info(f"Opening PC camera (device index: {self._index})")

        # On Windows, DirectShow (CAP_DSHOW) is more reliable than the
        # default MSMF backend — try it first, then fall back to default.
        backends = [(cv2.CAP_DSHOW, "DirectShow"), (None, "default")] if is_windows \
                   else [(None, "default")]

        for backend, name in backends:
            try:
                cap = cv2.VideoCapture(self._index, backend) if backend is not None \
                      else cv2.VideoCapture(self._index)

                if cap.isOpened():
                    # Verify we can actually read a frame
                    ok, _ = cap.read()
                    if ok:
                        self._cap = cap
                        logger.info(f"Camera opened with {name} backend")
                        break
                    else:
                        logger.warning(f"Camera opened but first read failed ({name} backend)")
                        cap.release()
                else:
                    cap.release()
                    logger.warning(f"Camera device {self._index} not opened with {name} backend")
            except Exception as e:
                logger.warning(f"Backend '{name}' raised: {e}")

        if self._cap is None or not self._cap.isOpened():
            logger.error(f"Failed to open camera device {self._index} on any backend")
            return False

        # Set preferred resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)

        # Reduce buffer size so we always get the latest frame
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"PC camera ready: {actual_w}x{actual_h}")
        return True

    def read_frame(self) -> tuple[bool, np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return False, np.zeros((self._height, self._width, 3), dtype=np.uint8)
        return self._cap.read()

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("PC camera released")

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def source_name(self) -> str:
        return f"PC Camera (device {self._index})"
