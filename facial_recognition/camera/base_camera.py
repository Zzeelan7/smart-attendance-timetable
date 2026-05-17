"""
camera/base_camera.py
Abstract base class that all camera sources must implement.
This ensures PC-Camera and ESP32-CAM are interchangeable.
"""

from abc import ABC, abstractmethod
import numpy as np


class BaseCamera(ABC):
    """
    Abstract camera interface.
    Any camera (PC webcam, ESP32-CAM, IP camera) must implement this.
    """

    @abstractmethod
    def start(self) -> bool:
        """Open / connect to the camera. Returns True on success."""
        ...

    @abstractmethod
    def read_frame(self) -> tuple[bool, np.ndarray]:
        """
        Read a single frame.
        Returns: (success: bool, frame: np.ndarray in BGR)
        """
        ...

    @abstractmethod
    def release(self):
        """Release / disconnect the camera."""
        ...

    @abstractmethod
    def is_opened(self) -> bool:
        """Check whether the camera is currently open."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name for this camera source."""
        ...
