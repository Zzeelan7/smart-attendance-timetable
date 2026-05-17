"""
app.py – Flask web server for the Facial Recognition System.

Routes:
  GET  /                  → Dashboard
  GET  /video_feed        → MJPEG stream (live annotated video)
  GET  /api/status        → JSON: camera + recognition status
  GET  /api/people        → JSON: list of enrolled people
  GET  /api/stats         → JSON: recognition stats
  GET  /api/log           → JSON: recent events
  POST /api/enroll        → Enroll from a captured frame (send name as JSON)
  POST /api/enroll_image  → Enroll from an uploaded image file
  POST /api/delete_person → Delete a person (send name as JSON)
  POST /api/rebuild       → Rebuild encodings from known_faces/ dir
  POST /api/set_camera    → Switch camera source at runtime
  GET  /api/snapshot      → Download current frame as JPEG
"""

import io
import os
import sys
import time
import logging
import threading
import traceback
import json
from datetime import datetime

import cv2
import numpy as np
from flask import (Flask, Response, jsonify, request,
                   render_template, send_file, stream_with_context)

# ── Path fix so imports work regardless of CWD ────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
from camera import get_camera
from camera.base_camera import BaseCamera
from recognition import FaceEngine
from recognition.logger import RecognitionLogger

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = config.SECRET_KEY

# ── Global state ──────────────────────────────────────────────────────────────
camera: BaseCamera | None = None
face_engine: FaceEngine   = FaceEngine()
rec_logger: RecognitionLogger = RecognitionLogger()

# Shared latest processed frame
_frame_lock = threading.Lock()
_latest_raw_frame: np.ndarray | None = None
_latest_annotated_frame: np.ndarray | None = None
_camera_info = {"source": str(config.CAMERA_SOURCE), "type": "PC Camera" if isinstance(config.CAMERA_SOURCE, int) else "ESP32-CAM"}
_is_running  = False
_last_results: list[dict] = []

# ── Camera thread ─────────────────────────────────────────────────────────────

def camera_loop():
    """Background thread: continuously read + process frames."""
    global camera, _latest_raw_frame, _latest_annotated_frame, _is_running, _last_results

    logger.info("Camera loop started")
    consecutive_failures = 0

    while _is_running:
        if camera is None or not camera.is_opened():
            time.sleep(0.1)
            continue

        ok, frame = camera.read_frame()
        if not ok or frame is None:
            consecutive_failures += 1
            if consecutive_failures > 30:
                logger.error("Too many frame failures – check camera connection")
                time.sleep(1.0)
                consecutive_failures = 0
            continue
        consecutive_failures = 0

        with _frame_lock:
            _latest_raw_frame = frame.copy()

        # Run recognition only if we have known faces (for performance)
        if face_engine.total_encodings > 0:
            annotated, results = face_engine.process_frame(frame)

            # Log new detections (throttled – max 1 per second per person)
            now = time.time()
            for r in results:
                rec_logger.log_event(
                    r["name"], r["confidence"],
                    r["is_known"], camera.source_name
                )

            with _frame_lock:
                _latest_annotated_frame = annotated
                _last_results = results
        else:
            # Just draw a "No known faces" overlay
            overlay = frame.copy()
            cv2.putText(overlay, "No enrolled faces – go to dashboard to enroll",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 200, 255), 2)
            with _frame_lock:
                _latest_annotated_frame = overlay
                _last_results = []

        time.sleep(0.03)  # ~30 fps cap

    logger.info("Camera loop stopped")


def start_camera(source=None):
    """Initialize and start the camera + processing thread."""
    global camera, _is_running

    stop_camera()
    time.sleep(0.3)

    camera = get_camera(source)
    if not camera.start():
        logger.error(f"Failed to start camera: {camera.source_name}")
        return False

    _is_running = True
    t = threading.Thread(target=camera_loop, daemon=True, name="CameraLoop")
    t.start()
    logger.info(f"Camera started: {camera.source_name}")
    return True


def stop_camera():
    """Stop the camera and processing thread."""
    global camera, _is_running
    _is_running = False
    time.sleep(0.2)
    if camera is not None:
        camera.release()
        camera = None


# ── Video streaming ───────────────────────────────────────────────────────────

def generate_frames():
    """MJPEG frame generator for /video_feed."""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
    while True:
        with _frame_lock:
            frame = _latest_annotated_frame

        if frame is None:
            # Send a placeholder frame
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Waiting for camera...",
                        (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (100, 100, 100), 2)
            frame = placeholder

        ok, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n"
               + buf.tobytes()
               + b"\r\n")
        time.sleep(0.033)   # 30 fps


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           camera_info=_camera_info,
                           known_people=face_engine.known_people)


@app.route("/video_feed")
def video_feed():
    return Response(
        stream_with_context(generate_frames()),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    cam_ok = camera is not None and camera.is_opened()
    with _frame_lock:
        results = _last_results.copy()
    return jsonify({
        "camera_ok":      cam_ok,
        "camera_source":  camera.source_name if cam_ok else "Not connected",
        "camera_type":    "ESP32-CAM" if (cam_ok and "http" in camera.source_name.lower()) else "PC Camera",
        "enrolled":       face_engine.total_encodings,
        "known_people":   face_engine.known_people,
        "is_running":     _is_running,
        "current_faces":  results,
        "timestamp":      datetime.now().isoformat(),
    })


@app.route("/api/people")
def api_people():
    people = []
    known_dir = config.KNOWN_FACES_DIR
    for name in face_engine.known_people:
        person_dir = os.path.join(known_dir, name)
        img_count = len([f for f in os.listdir(person_dir)
                         if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                        ) if os.path.isdir(person_dir) else 0
        enc_count = face_engine.known_names.count(name)
        people.append({"name": name, "images": img_count, "encodings": enc_count})
    return jsonify({"people": people, "total": len(people)})


@app.route("/api/stats")
def api_stats():
    return jsonify(rec_logger.get_stats())


@app.route("/api/log")
def api_log():
    n = request.args.get("n", 50, type=int)
    return jsonify({"events": rec_logger.get_recent(n)})


@app.route("/api/enroll", methods=["POST"])
def api_enroll():
    """Enroll from the current live camera frame."""
    data = request.get_json()
    name = (data or {}).get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    with _frame_lock:
        frame = _latest_raw_frame.copy() if _latest_raw_frame is not None else None

    if frame is None:
        return jsonify({"success": False, "error": "No camera frame available"}), 503

    ok = face_engine.enroll_from_frame(name, frame)
    if ok:
        return jsonify({"success": True, "message": f"'{name}' enrolled successfully",
                        "total_encodings": face_engine.total_encodings})
    return jsonify({"success": False, "error": "No face detected in frame. Position your face clearly."}), 400


@app.route("/api/enroll_image", methods=["POST"])
def api_enroll_image():
    """Enroll from an uploaded image file."""
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image file uploaded"}), 400

    file = request.files["image"]
    person_dir = os.path.join(config.KNOWN_FACES_DIR, name)
    os.makedirs(person_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(person_dir, f"{stamp}_{file.filename}")
    file.save(save_path)

    ok = face_engine.enroll_from_image(name, save_path)
    if ok:
        return jsonify({"success": True, "message": f"'{name}' enrolled from image",
                        "total_encodings": face_engine.total_encodings})
    return jsonify({"success": False, "error": "No face found in the uploaded image"}), 400


@app.route("/api/delete_person", methods=["POST"])
def api_delete_person():
    data = request.get_json()
    name = (data or {}).get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400
    ok = face_engine.delete_person(name)
    return jsonify({"success": ok,
                    "message": f"'{name}' deleted" if ok else f"'{name}' not found"})


@app.route("/api/rebuild", methods=["POST"])
def api_rebuild():
    count = face_engine.rebuild_from_known_faces_dir()
    return jsonify({"success": True, "count": count,
                    "message": f"Rebuilt {count} encoding(s) from known_faces/"})


@app.route("/api/set_camera", methods=["POST"])
def api_set_camera():
    """Switch camera source at runtime."""
    data   = request.get_json()
    source = (data or {}).get("source")
    if source is None:
        return jsonify({"success": False, "error": "source is required"}), 400

    # Convert to int if it looks like a device index
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    ok = start_camera(source)
    global _camera_info
    _camera_info = {
        "source": str(source),
        "type":   "ESP32-CAM" if isinstance(source, str) and source.startswith("http") else "PC Camera",
    }
    return jsonify({"success": ok, "source": str(source)})


@app.route("/api/snapshot")
def api_snapshot():
    """Download the current frame as a JPEG."""
    with _frame_lock:
        frame = _latest_annotated_frame

    if frame is None:
        return jsonify({"error": "No frame available"}), 503

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        return jsonify({"error": "Encoding failed"}), 500

    return send_file(
        io.BytesIO(buf.tobytes()),
        mimetype="image/jpeg",
        as_attachment=True,
        download_name=f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
    )


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(" Facial Recognition System")
    logger.info(f" Camera source : {config.CAMERA_SOURCE}")
    logger.info(f" Enrolled      : {face_engine.total_encodings} face(s)")
    logger.info(f" Dashboard     : http://localhost:{config.PORT}")
    logger.info("=" * 60)

    # Start camera in background
    ok = start_camera()
    if not ok:
        logger.warning("Camera failed to start. You can set one via the web dashboard.")

    try:
        app.run(host=config.HOST, port=config.PORT,
                debug=config.DEBUG, threaded=True, use_reloader=False)
    finally:
        stop_camera()
