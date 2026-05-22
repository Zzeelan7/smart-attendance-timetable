"""
recognition/face_engine.py
Core facial recognition engine.

Primary backend  : face_recognition (dlib) — high accuracy
Fallback backend : OpenCV Haar Cascade  — works without dlib/Python 3.13

The app starts and the camera shows ONLINE regardless of which backend
is available.  If face_recognition is missing, detection still works
(bounding boxes drawn) but identity matching returns "Unknown".
"""

import os
import threading
import cv2
import pickle
import logging
import numpy as np
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# ── Try importing the dlib-based backend ────────────────────────────────────
try:
    import face_recognition as _fr
    _FR_AVAILABLE = True
    logger.info("face_recognition backend loaded (dlib).")
except ImportError:
    _fr = None
    _FR_AVAILABLE = False
    logger.warning(
        "face_recognition / dlib not installed — falling back to OpenCV Haar Cascade.\n"
        "  Recognition will detect faces but cannot identify individuals.\n"
        "  To enable full recognition install dlib:\n"
        "    pip install face-recognition"
    )

# ── OpenCV Haar Cascade (always available) ───────────────────────────────────
_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_haar = cv2.CascadeClassifier(_CASCADE_PATH)


class FaceEngine:
    """
    Manages:
      - Loading / saving known face encodings
      - Detecting faces in a frame
      - Recognising detected faces (dlib backend only)
      - Drawing annotated overlays on frames
      - Enrolling new faces from images or live capture
    """

    def __init__(self):
        self.known_names:     list[str]        = []
        self.known_encodings: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._ensure_dirs()
        self.load_encodings()

    # ─── Directory setup ──────────────────────────────────────────────────

    def _ensure_dirs(self):
        os.makedirs(config.KNOWN_FACES_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(config.ENCODINGS_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)

    # ─── Encoding persistence ─────────────────────────────────────────────

    def load_encodings(self) -> int:
        """Load encodings from the pickle cache. Returns count loaded."""
        if not _FR_AVAILABLE:
            return 0
        if not os.path.exists(config.ENCODINGS_FILE):
            logger.info("No encodings file found — starting fresh.")
            return 0
        try:
            with open(config.ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)
            self.known_names     = data.get("names", [])
            self.known_encodings = data.get("encodings", [])
            logger.info(f"Loaded {len(self.known_names)} known face(s).")
            return len(self.known_names)
        except Exception as e:
            logger.error(f"Failed to load encodings: {e}")
            return 0

    def save_encodings(self):
        """Persist encodings to disk."""
        if not _FR_AVAILABLE:
            return
        with open(config.ENCODINGS_FILE, "wb") as f:
            pickle.dump({
                "names":     self.known_names,
                "encodings": self.known_encodings,
            }, f)
        logger.info(f"Saved {len(self.known_names)} encoding(s).")

    # ─── Enrollment ───────────────────────────────────────────────────────

    def enroll_from_image(self, name: str, image_path: str) -> bool:
        """
        Enroll a person from an image file.
        Requires face_recognition backend.
        """
        if not _FR_AVAILABLE:
            logger.warning("Enrollment unavailable — face_recognition not installed.")
            return False
        img = _fr.load_image_file(image_path)
        with self._lock:
            encodings = _fr.face_encodings(img, num_jitters=1, model="large")
        if not encodings:
            logger.warning(f"No face found in {image_path}")
            return False
        if len(encodings) > 1:
            logger.warning(f"Multiple faces in {image_path} — using the first")
        self.known_names.append(name)
        self.known_encodings.append(encodings[0])
        self.save_encodings()
        logger.info(f"Enrolled '{name}' from {image_path}")
        return True

    def enroll_from_frame(self, name: str, frame: np.ndarray) -> bool:
        """
        Enroll a person from a live camera frame (BGR).
        Requires face_recognition backend.
        """
        if not _FR_AVAILABLE:
            logger.warning("Enrollment unavailable — face_recognition not installed.")
            return False
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with self._lock:
            locations = _fr.face_locations(
                rgb,
                number_of_times_to_upsample=config.UPSAMPLE_TIMES,
                model=config.DETECTION_MODEL,
            )
            encodings = _fr.face_encodings(rgb, locations, num_jitters=1)
        if not encodings:
            logger.warning("No face detected in frame for enrollment")
            return False

        enc = encodings[0] if len(encodings) == 1 \
              else self._largest_face_encoding(encodings, locations)
        self.known_names.append(name)
        self.known_encodings.append(enc)

        person_dir = os.path.join(config.KNOWN_FACES_DIR, name)
        os.makedirs(person_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(person_dir, f"{stamp}.jpg")
        top, right, bottom, left = locations[0]
        face_crop = frame[top:bottom, left:right]
        cv2.imwrite(img_path, face_crop)

        self.save_encodings()
        logger.info(f"Enrolled '{name}' from live frame → {img_path}")
        return True

    def rebuild_from_known_faces_dir(self) -> int:
        """Scan known_faces/ and re-encode all images. Returns count built."""
        if not _FR_AVAILABLE:
            logger.warning("Rebuild unavailable — face_recognition not installed.")
            return 0
        self.known_names.clear()
        self.known_encodings.clear()

        known_dir = Path(config.KNOWN_FACES_DIR)
        for person_dir in sorted(known_dir.iterdir()):
            if not person_dir.is_dir():
                continue
            name = person_dir.name
            for img_file in sorted(person_dir.glob("*.*")):
                if img_file.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                    continue
                try:
                    img  = _fr.load_image_file(str(img_file))
                    encs = _fr.face_encodings(img)
                    if encs:
                        self.known_names.append(name)
                        self.known_encodings.append(encs[0])
                        logger.debug(f"  ✓ {name}: {img_file.name}")
                except Exception as e:
                    logger.warning(f"  ✗ Skipped {img_file}: {e}")

        self.save_encodings()
        logger.info(f"Rebuilt: {len(self.known_names)} encoding(s) from known_faces/")
        return len(self.known_names)

    def delete_person(self, name: str) -> bool:
        """Remove all encodings and images for a given person."""
        import shutil
        indices = [i for i, n in enumerate(self.known_names) if n == name]
        for i in reversed(indices):
            self.known_names.pop(i)
            self.known_encodings.pop(i)
        if _FR_AVAILABLE:
            self.save_encodings()
        person_dir = os.path.join(config.KNOWN_FACES_DIR, name)
        if os.path.isdir(person_dir):
            shutil.rmtree(person_dir)
        logger.info(f"Deleted '{name}' ({len(indices)} encoding(s) removed)")
        return len(indices) > 0

    # ─── Recognition ─────────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict]]:
        """
        Detect and recognise all faces in a BGR frame.

        Returns:
            annotated_frame : BGR frame with boxes and labels drawn
            results         : list of dicts [{name, confidence, location, is_known}]
        """
        if _FR_AVAILABLE:
            return self._process_frame_dlib(frame)
        return self._process_frame_opencv(frame)

    # ── dlib / face_recognition path ──────────────────────────────────────

    def _process_frame_dlib(self, frame: np.ndarray):
        small      = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small  = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        with self._lock:
            locations = _fr.face_locations(
                rgb_small,
                number_of_times_to_upsample=config.UPSAMPLE_TIMES,
                model=config.DETECTION_MODEL,
            )
            encodings = _fr.face_encodings(rgb_small, locations)

        results  = []
        annotated = frame.copy()
        for (top, right, bottom, left), enc in zip(locations, encodings):
            top    *= 2; right  *= 2
            bottom *= 2; left   *= 2
            name, confidence, is_known = self._identify(enc)
            results.append({
                "name":       name,
                "confidence": round(confidence * 100, 1),
                "location":   (top, right, bottom, left),
                "is_known":   is_known,
            })
            self._draw_face_box(annotated, top, right, bottom, left,
                                name, confidence, is_known)
        return annotated, results

    # ── OpenCV Haar Cascade fallback path ─────────────────────────────────

    def _process_frame_opencv(self, frame: np.ndarray):
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
        faces = _haar.detectMultiScale(
            small, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        results  = []
        annotated = frame.copy()

        for (x, y, w, h) in faces:
            # Scale back to full resolution
            x, y, w, h = x*2, y*2, w*2, h*2
            top, right, bottom, left = y, x+w, y+h, x
            results.append({
                "name":       "Unknown",
                "confidence": 0.0,
                "location":   (top, right, bottom, left),
                "is_known":   False,
            })
            # Draw corner-accent box
            self._draw_face_box(annotated, top, right, bottom, left,
                                "Unknown (install dlib)", 0.0, False)

        # Watermark so the user knows recognition is limited
        if faces is not None and len(faces) > 0:
            cv2.putText(annotated, "Recognition limited — dlib not installed",
                        (10, annotated.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
        return annotated, results

    # ── Identification helper (dlib only) ─────────────────────────────────

    def _identify(self, encoding: np.ndarray) -> tuple[str, float, bool]:
        if not self.known_encodings:
            return "Unknown", 0.0, False
        distances = _fr.face_distance(self.known_encodings, encoding)
        best_idx  = int(np.argmin(distances))
        best_dist = float(distances[best_idx])
        confidence = max(0.0, 1.0 - best_dist)
        if best_dist <= config.RECOGNITION_THRESHOLD:
            return self.known_names[best_idx], confidence, True
        return "Unknown", confidence, False

    # ─── Drawing helpers ──────────────────────────────────────────────────

    def _draw_face_box(self, frame, top, right, bottom, left,
                       name, confidence, is_known):
        color      = (0, 220, 100) if is_known else (0, 80, 255)
        thickness  = 2
        corner_len = 20
        pts = [(left, top), (right, top), (right, bottom), (left, bottom)]
        for px, py in pts:
            dx = 1 if px == left  else -1
            dy = 1 if py == top   else -1
            cv2.line(frame, (px, py), (px + dx*corner_len, py), color, thickness+1)
            cv2.line(frame, (px, py), (px, py + dy*corner_len), color, thickness+1)

        label = f"{name}  {confidence*100:.0f}%" if confidence else name
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(frame,
                      (left, bottom),
                      (left + tw + 10, bottom + th + 12),
                      color, -1)
        cv2.putText(frame, label,
                    (left + 5, bottom + th + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 2)

    @staticmethod
    def _largest_face_encoding(encodings, locations):
        sizes = [(b - t) * (r - l) for (t, r, b, l) in locations]
        return encodings[int(np.argmax(sizes))]

    # ─── Properties ──────────────────────────────────────────────────────

    @property
    def known_people(self) -> list[str]:
        return sorted(set(self.known_names))

    @property
    def total_encodings(self) -> int:
        return len(self.known_encodings)

    @property
    def backend(self) -> str:
        return "face_recognition (dlib)" if _FR_AVAILABLE else "OpenCV Haar Cascade"
