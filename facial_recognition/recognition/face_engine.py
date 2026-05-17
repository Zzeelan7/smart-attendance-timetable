"""
recognition/face_engine.py
Core facial recognition engine.

Uses:
  - face_recognition (dlib) for encoding and comparison
  - OpenCV for drawing overlays
  - pickle for fast encoding persistence
"""

import os
import threading
import cv2
import pickle
import logging
import numpy as np
import face_recognition
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class FaceEngine:
    """
    Manages:
      - Loading / saving known face encodings
      - Detecting faces in a frame
      - Recognising detected faces
      - Drawing annotated overlays on frames
      - Enrolling new faces from images or live capture
    """

    def __init__(self):
        self.known_names:     list[str]             = []
        self.known_encodings: list[np.ndarray]      = []
        self._lock = threading.Lock()   # Serialise all face_recognition calls
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
        The image should contain exactly one face.

        Returns True if enrollment succeeded.
        """
        img = face_recognition.load_image_file(image_path)
        with self._lock:
            encodings = face_recognition.face_encodings(
                img, num_jitters=1, model="large"
            )
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
        Returns True if a face was found and enrolled.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with self._lock:
            locations = face_recognition.face_locations(
                rgb, number_of_times_to_upsample=config.UPSAMPLE_TIMES,
                model=config.DETECTION_MODEL
            )
            encodings = face_recognition.face_encodings(rgb, locations, num_jitters=1)

        if not encodings:
            logger.warning("No face detected in frame for enrollment")
            return False

        # Pick the largest face (closest to camera)
        enc = encodings[0] if len(encodings) == 1 else self._largest_face_encoding(encodings, locations)
        self.known_names.append(name)
        self.known_encodings.append(enc)

        # Also save the face image to known_faces/
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
        """
        Scan the known_faces/ directory and re-encode all images.
        Useful after manually adding photos.
        Returns number of encodings built.
        """
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
                    img = face_recognition.load_image_file(str(img_file))
                    encs = face_recognition.face_encodings(img)
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
        # Remove from memory
        indices = [i for i, n in enumerate(self.known_names) if n == name]
        for i in reversed(indices):
            self.known_names.pop(i)
            self.known_encodings.pop(i)
        self.save_encodings()

        # Remove image folder
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
            annotated_frame: BGR frame with boxes and labels drawn
            results: list of dicts [{name, confidence, location, is_known}]
        """
        # Downsample for faster detection
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        with self._lock:
            locations = face_recognition.face_locations(
                rgb_small,
                number_of_times_to_upsample=config.UPSAMPLE_TIMES,
                model=config.DETECTION_MODEL,
            )
            encodings = face_recognition.face_encodings(rgb_small, locations)

        results = []
        annotated = frame.copy()

        for (top, right, bottom, left), enc in zip(locations, encodings):
            # Scale back to original frame size
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

    def _identify(self, encoding: np.ndarray) -> tuple[str, float, bool]:
        """
        Match an encoding against known faces.
        Returns: (name, confidence_0_to_1, is_known)
        """
        if not self.known_encodings:
            return "Unknown", 0.0, False

        distances = face_recognition.face_distance(self.known_encodings, encoding)
        best_idx  = int(np.argmin(distances))
        best_dist = float(distances[best_idx])

        # Convert distance to a 0-1 confidence (distance=0 → 1.0, distance≥1 → 0.0)
        confidence = max(0.0, 1.0 - best_dist)

        if best_dist <= config.RECOGNITION_THRESHOLD:
            return self.known_names[best_idx], confidence, True
        return "Unknown", confidence, False

    # ─── Drawing helpers ──────────────────────────────────────────────────

    def _draw_face_box(self, frame, top, right, bottom, left,
                       name, confidence, is_known):
        """Draw a styled bounding box and label on the frame."""
        color = (0, 220, 100) if is_known else (0, 80, 255)   # green / red
        thickness = 2

        # Rounded-corner box (4 corner accents)
        corner_len = 20
        pts = [(left, top), (right, top), (right, bottom), (left, bottom)]
        for px, py in pts:
            dx = 1 if px == left  else -1
            dy = 1 if py == top   else -1
            cv2.line(frame, (px, py), (px + dx * corner_len, py), color, thickness + 1)
            cv2.line(frame, (px, py), (px, py + dy * corner_len), color, thickness + 1)

        # Label background
        label = f"{name}  {confidence*100:.0f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame,
                      (left, bottom),
                      (left + tw + 10, bottom + th + 12),
                      color, -1)
        cv2.putText(frame, label,
                    (left + 5, bottom + th + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2)

    @staticmethod
    def _largest_face_encoding(encodings, locations):
        """Return the encoding for the largest detected face."""
        sizes = [(b - t) * (r - l) for (t, r, b, l) in locations]
        return encodings[int(np.argmax(sizes))]

    # ─── Properties ──────────────────────────────────────────────────────

    @property
    def known_people(self) -> list[str]:
        """Deduplicated list of enrolled person names."""
        return sorted(set(self.known_names))

    @property
    def total_encodings(self) -> int:
        return len(self.known_encodings)
