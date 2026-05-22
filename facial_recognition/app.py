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

    try:
        camera = get_camera(source)
        if not camera.start():
            logger.warning(f"Failed to start camera: {camera.source_name}")
            logger.warning("Camera will be unavailable - use image upload for enrollment instead")
            return False

        _is_running = True
        t = threading.Thread(target=camera_loop, daemon=True, name="CameraLoop")
        t.start()
        logger.info(f"Camera started: {camera.source_name}")
        return True
    except Exception as e:
        logger.error(f"Exception starting camera: {e}")
        logger.warning("Camera initialization failed - image enrollment will still work")
        return False


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
    from recognition.face_engine import _FR_AVAILABLE
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
        "face_recognition_available": _FR_AVAILABLE,
        "enrollment_available": _FR_AVAILABLE,
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
    from recognition.face_engine import _FR_AVAILABLE
    
    if not _FR_AVAILABLE:
        return jsonify({"success": False, "error": "face_recognition not available - use image enrollment"}), 503
    
    data = request.get_json()
    name = (data or {}).get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    with _frame_lock:
        frame = _latest_raw_frame.copy() if _latest_raw_frame is not None else None

    if frame is None:
        return jsonify({"success": False, "error": "Camera not available - please enable your camera or use image enrollment"}), 503

    ok = face_engine.enroll_from_frame(name, frame)
    if ok:
        logger.info(f"Successfully enrolled '{name}' from camera frame")
        return jsonify({"success": True, "message": f"'{name}' enrolled successfully",
                        "total_encodings": face_engine.total_encodings})
    logger.warning(f"Enrollment failed for '{name}' - no face detected or error occurred")
    return jsonify({"success": False, "error": "No face detected in frame. Position your face clearly in the camera."}), 400


@app.route("/api/enroll_image", methods=["POST"])
def api_enroll_image():
    """Enroll from an uploaded image file."""
    from recognition.face_engine import _FR_AVAILABLE
    
    if not _FR_AVAILABLE:
        return jsonify({"success": False, "error": "face_recognition not available - enrollment disabled"}), 503
    
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image file uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    person_dir = os.path.join(config.KNOWN_FACES_DIR, name)
    os.makedirs(person_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(person_dir, f"{stamp}_{file.filename}")
    
    try:
        file.save(save_path)
        ok = face_engine.enroll_from_image(name, save_path)
        if ok:
            logger.info(f"Successfully enrolled '{name}' from image")
            return jsonify({"success": True, "message": f"'{name}' enrolled from image",
                            "total_encodings": face_engine.total_encodings})
        logger.warning(f"Enrollment failed for '{name}' - no face found in image")
        return jsonify({"success": False, "error": "No face found in the uploaded image. Ensure the image has a clear, front-facing face."}), 400
    except Exception as e:
        logger.error(f"Error enrolling from image: {e}")
        return jsonify({"success": False, "error": f"Enrollment error: {str(e)}"}), 500


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


# ── ESP32 state machine ───────────────────────────────────────────────────────
# Shared state that the ESP32 polls every ~1 s.
# Updated by camera_loop when a face is detected / lost.
import uuid
_esp32_lock  = threading.Lock()
_esp32_state = {
    "state":      "idle",   # idle | face_detected | not_registered
    "name":       None,
    "confidence": 0.0,
    "timestamp":  None,
}
_ESP32_RESET_AFTER = 12   # seconds — auto-reset to idle after this long

# Path helpers
DATA_DIR          = os.path.join(BASE_DIR, "data")
STUDENTS_DB_PATH  = os.path.join(DATA_DIR, "students_db.json")
ATTENDANCE_PATH   = os.path.join(DATA_DIR, "attendance_log.json")
TIMETABLE_PATH    = os.path.join(
    os.path.dirname(BASE_DIR), "timetable_maker", "last_result.json"
)
os.makedirs(DATA_DIR, exist_ok=True)

def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _set_esp32_state(state: str, name=None, confidence=0.0):
    with _esp32_lock:
        _esp32_state["state"]      = state
        _esp32_state["name"]       = name
        _esp32_state["confidence"] = round(confidence, 3)
        _esp32_state["timestamp"]  = datetime.now().isoformat()

# ── Hook camera_loop to update ESP32 state ────────────────────────────────────
# Monkey-patch camera_loop's result handler after-the-fact using a watcher thread

def _esp32_watcher():
    """
    Watches _last_results every 0.5 s and pushes state changes so the
    ESP32 poll endpoint always reflects the latest recognition result.
    Auto-resets to idle if no update arrives within _ESP32_RESET_AFTER seconds.
    """
    prev_state = "idle"
    last_detection_time = 0.0

    while True:
        time.sleep(0.5)
        with _frame_lock:
            results = list(_last_results)

        known = [r for r in results if r.get("is_known")]
        unknown = [r for r in results if not r.get("is_known")]

        if known:
            best = max(known, key=lambda r: r.get("confidence", 0))
            _set_esp32_state("face_detected", best["name"], best.get("confidence", 0))
            last_detection_time = time.time()
            prev_state = "face_detected"
        elif unknown:
            _set_esp32_state("not_registered")
            last_detection_time = time.time()
            prev_state = "not_registered"
        else:
            # Auto-reset to idle after timeout
            if prev_state != "idle" and (time.time() - last_detection_time) > _ESP32_RESET_AFTER:
                _set_esp32_state("idle")
                prev_state = "idle"


threading.Thread(target=_esp32_watcher, daemon=True, name="ESP32Watcher").start()


# ── Timetable helpers ─────────────────────────────────────────────────────────

def _find_student(name: str) -> dict:
    """Return {semester, section} for a student name, or {} if not found."""
    db = _load_json(STUDENTS_DB_PATH, {})
    name_lower = name.lower()
    for sem, sections in db.items():
        for sec, students in sections.items():
            for s in students:
                if s.get("name", "").lower() == name_lower:
                    return {"semester": sem, "section": sec, "usn": s.get("usn", "")}
    return {}

PERIOD_TIMES = ["9:00-10:00","10:00-11:00","11:15-12:15",
                "12:15-1:15","2:00-3:00","3:00-4:00"]
PERIOD_LABELS = ["P1","P2","P3","P4","P5","P6"]
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday"]

def _get_today_timetable(name: str) -> dict:
    """Return today's classes for the given student/teacher name."""
    today = datetime.now().strftime("%A")   # e.g. "Thursday"

    # Try to find in student DB
    info = _find_student(name)
    result_data = _load_json(TIMETABLE_PATH, {})
    if not result_data:
        return {"name": name, "day": today, "classes": [], "error": "No timetable generated yet"}

    classes = []
    if info:
        sem_key = info["semester"]
        section = info["section"]
        sem_result = result_data.get("results", {}).get(sem_key, {})
        grid_key = f"grid_{section}"
        grid = sem_result.get(grid_key, [])
        day_idx = DAYS.index(today) if today in DAYS else -1
        if day_idx >= 0 and day_idx < len(grid):
            for p_idx, slot in enumerate(grid[day_idx]):
                if slot and not slot.get("cont"):
                    classes.append({
                        "period":  PERIOD_LABELS[p_idx],
                        "time":    PERIOD_TIMES[p_idx] if p_idx < len(PERIOD_TIMES) else "",
                        "subject": slot.get("full_name", slot.get("display", "")),
                        "teacher": slot.get("teacher", ""),
                        "type":    slot.get("type", "theory"),
                    })
    else:
        # Try as teacher — search all sems
        for sem_key, sem_result in result_data.get("results", {}).items():
            ts = sem_result.get("teacher_schedules", {})
            if name in ts:
                day_idx = DAYS.index(today) if today in DAYS else -1
                for sec in ("A", "B"):
                    grid = ts[name].get(sec, [])
                    if day_idx >= 0 and day_idx < len(grid):
                        for p_idx, slot in enumerate(grid[day_idx]):
                            if slot and not slot.get("cont"):
                                classes.append({
                                    "period":  PERIOD_LABELS[p_idx],
                                    "time":    PERIOD_TIMES[p_idx] if p_idx < len(PERIOD_TIMES) else "",
                                    "subject": slot.get("full_name", slot.get("display", "")),
                                    "section": f"Sem {sem_key} Sec {sec}",
                                    "type":    slot.get("type", "theory"),
                                })

    return {"name": name, "day": today, "classes": classes, "info": info}


# ── New API routes ─────────────────────────────────────────────────────────────

@app.route("/api/esp32/poll")
def esp32_poll():
    """ESP32 calls this every ~1 s to get the current recognition state."""
    with _esp32_lock:
        state = dict(_esp32_state)
    return jsonify(state)


@app.route("/api/esp32/reset", methods=["POST"])
def esp32_reset():
    """ESP32 calls this after it has finished handling a detection event."""
    _set_esp32_state("idle")
    return jsonify({"ok": True})


@app.route("/api/attendance/mark", methods=["POST"])
def attendance_mark():
    """
    Called by the ESP32 after fingerprint verification.
    Body JSON: { name, fingerprint_id, semester (opt), section (opt) }
    Returns:   { success, message, timetable }
    """
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "name required"}), 400

    now      = datetime.now()
    info     = _find_student(name)
    day_name = now.strftime("%A")

    # Build a record
    record = {
        "id":           str(uuid.uuid4())[:8],
        "name":         name,
        "usn":          info.get("usn", data.get("usn", "")),
        "semester":     info.get("semester", data.get("semester", "")),
        "section":      info.get("section", data.get("section", "")),
        "date":         now.strftime("%Y-%m-%d"),
        "day":          day_name,
        "time":         now.strftime("%H:%M:%S"),
        "timestamp":    now.isoformat(),
        "fingerprint_id": data.get("fingerprint_id", ""),
        "verification": "face+fingerprint",
    }

    log = _load_json(ATTENDANCE_PATH, {"records": []})
    log["records"].append(record)
    _save_json(ATTENDANCE_PATH, log)

    # Reset ESP32 state
    _set_esp32_state("idle")

    # Return timetable for this person
    tt = _get_today_timetable(name)
    return jsonify({"success": True, "message": "Attendance marked", "record": record, "timetable": tt})


@app.route("/api/timetable/<name>")
def api_timetable(name):
    """Return today's timetable for a given student or teacher name."""
    return jsonify(_get_today_timetable(name))


@app.route("/api/students", methods=["GET"])
def api_students_get():
    """Return the full student database, or filter by ?sem=4."""
    db = _load_json(STUDENTS_DB_PATH, {})
    sem = request.args.get("sem")
    if sem:
        return jsonify(db.get(str(sem), {}))
    return jsonify(db)


@app.route("/api/students", methods=["POST"])
def api_students_post():
    """
    Save/merge student data for a semester.
    Body: { semester: "4", section: "A", students: [{name, usn}, ...] }
    """
    data    = request.get_json(force=True) or {}
    sem     = str(data.get("semester", "")).strip()
    section = data.get("section", "A").upper()
    students = data.get("students", [])
    if not sem:
        return jsonify({"success": False, "error": "semester required"}), 400

    db = _load_json(STUDENTS_DB_PATH, {})
    db.setdefault(sem, {})
    db[sem][section] = students
    _save_json(STUDENTS_DB_PATH, db)
    return jsonify({"success": True, "count": len(students)})


@app.route("/api/students/sync")
def api_students_sync():
    """
    Read student lists from the Timetable Maker's wizard_state.json
    and merge them into the local students_db.json.
    """
    wizard_path = os.path.join(
        os.path.dirname(BASE_DIR), "timetable_maker", "wizard_state.json"
    )
    if not os.path.exists(wizard_path):
        return jsonify({"success": False, "error": "No wizard_state.json found — generate a timetable first"}), 404

    with open(wizard_path, encoding="utf-8") as f:
        wizard = json.load(f)

    wizard_students = wizard.get("students", {})
    db = _load_json(STUDENTS_DB_PATH, {})
    imported = 0
    for sem, sections in wizard_students.items():
        db.setdefault(sem, {})
        for sec, students in sections.items():
            db[sem][sec] = students
            imported += len(students)
    _save_json(STUDENTS_DB_PATH, db)
    return jsonify({"success": True, "imported": imported, "semesters": list(wizard_students.keys())})


@app.route("/api/attendance/log")
def api_attendance_log():
    """Return attendance records. Optional filters: ?date=2026-05-21&sem=4&name=John"""
    log = _load_json(ATTENDANCE_PATH, {"records": []})
    records = log.get("records", [])
    date_f  = request.args.get("date")
    sem_f   = request.args.get("sem")
    name_f  = request.args.get("name", "").lower()
    if date_f:
        records = [r for r in records if r.get("date") == date_f]
    if sem_f:
        records = [r for r in records if str(r.get("semester")) == str(sem_f)]
    if name_f:
        records = [r for r in records if name_f in r.get("name","").lower()]
    return jsonify({"records": records, "total": len(records)})


# ── New page routes ───────────────────────────────────────────────────────────

@app.route("/students")
def students_page():
    db = _load_json(STUDENTS_DB_PATH, {})
    semesters = sorted(db.keys(), key=lambda x: int(x) if x.isdigit() else 0)
    return render_template("students.html", semesters=semesters, db=db)


@app.route("/attendance")
def attendance_page():
    log     = _load_json(ATTENDANCE_PATH, {"records": []})
    records = sorted(log.get("records", []), key=lambda r: r.get("timestamp",""), reverse=True)
    return render_template("attendance.html", records=records)


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

