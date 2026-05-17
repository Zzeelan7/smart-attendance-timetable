"""
camera/camera_factory.py
Factory function – reads config and returns the correct camera instance.
Switching cameras = changing ONE value in config.py.
"""

import logging
from .base_camera import BaseCamera

logger = logging.getLogger(__name__)


def get_camera(source=None) -> BaseCamera:
    """
    Create and return the appropriate camera based on config.CAMERA_SOURCE.

    Args:
        source: Override config.CAMERA_SOURCE (optional). Pass 0 for PC
                webcam or a URL string for ESP32-CAM.

    Returns:
        A BaseCamera instance (not yet started – call .start() yourself).
    """
    import config  # local import to avoid circular deps

    src = source if source is not None else config.CAMERA_SOURCE

    if isinstance(src, int):
        # ── PC / USB webcam ────────────────────────────────────────────────
        from .pc_camera import PCCamera
        logger.info(f"Camera factory → PCCamera (device {src})")
        return PCCamera(
            device_index=src,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
        )

    elif isinstance(src, str) and src.startswith("http"):
        # ── ESP32-CAM (MJPEG stream) ───────────────────────────────────────
        from .esp32_camera import ESP32Camera
        logger.info(f"Camera factory → ESP32Camera ({src})")
        return ESP32Camera(
            stream_url=src,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
        )

    else:
        raise ValueError(
            f"Unknown CAMERA_SOURCE: {src!r}\n"
            "Use an integer for PC webcam or an http:// URL for ESP32-CAM."
        )
