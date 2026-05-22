#!/usr/bin/env python3
"""
Windows Camera Server - Capture webcam and stream to Docker containers via HTTP.
Run this on your Windows host machine to make your webcam available to Docker.

Usage:
  python windows_camera_server.py [--port 8765] [--camera 0]

Then set in your docker-compose: CAMERA_SOURCE=http://host.docker.internal:8765/stream
"""

import cv2
import argparse
import threading
from flask import Flask, Response, jsonify
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global camera state
camera = None
latest_frame = None
frame_lock = threading.Lock()
camera_ready = False

def init_camera(device_index=0):
    global camera, camera_ready
    try:
        logger.info(f"Attempting to open camera device {device_index}...")
        
        # Try with default backend first
        cap = cv2.VideoCapture(device_index)
        
        if not cap.isOpened():
            logger.warning(f"Failed with default backend, trying DirectShow...")
            # Try DirectShow backend explicitly (Windows)
            cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        
        if not cap.isOpened():
            logger.error(f"Failed to open camera device {device_index} with any backend")
            return False
        
        # Set camera properties for better performance
        logger.info("Setting camera resolution and FPS...")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Test reading a frame
        logger.info("Testing frame capture...")
        ret, test_frame = cap.read()
        if not ret or test_frame is None:
            logger.error("Failed to read test frame from camera")
            cap.release()
            return False
        
        camera = cap
        camera_ready = True
        logger.info(f"✓ Camera device {device_index} initialized successfully - resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        return True
    except Exception as e:
        logger.error(f"Exception initializing camera: {e}")
        import traceback
        traceback.print_exc()
        return False

def camera_thread_loop():
    """Continuously capture frames from camera."""
    global latest_frame, camera, camera_ready
    
    if not camera_ready or camera is None:
        return
    
    logger.info("Camera capture thread started")
    frame_count = 0
    
    while camera_ready and camera is not None:
        try:
            ret, frame = camera.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                continue
            
            with frame_lock:
                latest_frame = frame.copy()
            
            frame_count += 1
            if frame_count % 100 == 0:
                logger.info(f"Captured {frame_count} frames")
        except Exception as e:
            logger.error(f"Camera read error: {e}")
            break
    
    logger.info("Camera capture thread stopped")

def generate_frames():
    """Generate MJPEG stream of camera frames."""
    while True:
        with frame_lock:
            if latest_frame is None:
                continue
            frame = latest_frame.copy()
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n'
               + frame_bytes + b'\r\n')

@app.route('/stream')
def stream():
    """MJPEG stream endpoint."""
    return Response(generate_frames(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Check camera status."""
    with frame_lock:
        has_frame = latest_frame is not None
    
    return jsonify({
        'status': 'ready' if camera_ready and has_frame else 'initializing',
        'camera_ready': camera_ready,
        'has_frame': has_frame
    })

@app.route('/')
def index():
    """Simple status page."""
    return '''
    <html>
    <head>
        <title>Windows Camera Server</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status.ok { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
            img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 20px 0; }
            code { background: #f8f9fa; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📹 Windows Camera Server</h1>
            <div id="status" class="status"></div>
            <h2>Live Stream</h2>
            <img id="stream" src="/stream" alt="Camera Stream" />
            <h2>Usage</h2>
            <p>In your Docker container, set the camera source to:</p>
            <code>CAMERA_SOURCE=http://host.docker.internal:8765/stream</code>
        </div>
        <script>
            function updateStatus() {
                fetch('/status')
                    .then(r => r.json())
                    .then(data => {
                        const el = document.getElementById('status');
                        el.className = 'status ' + (data.camera_ready ? 'ok' : 'error');
                        el.textContent = '✓ Camera Ready' if data.camera_ready else '✗ Camera Not Ready';
                    });
            }
            updateStatus();
            setInterval(updateStatus, 2000);
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Windows Camera Server for Docker')
    parser.add_argument('--port', type=int, default=8765, help='Port to run server on (default: 8765)')
    parser.add_argument('--camera', type=int, default=0, help='Camera device index (default: 0)')
    args = parser.parse_args()
    
    logger.info(f"Starting Windows Camera Server on port {args.port}...")
    logger.info(f"Using camera device: {args.camera}")
    
    # Initialize camera
    if not init_camera(args.camera):
        logger.error("Failed to initialize camera. Exiting.")
        exit(1)
    
    # Start camera capture thread
    capture_thread = threading.Thread(target=camera_thread_loop, daemon=True, name="CameraCapture")
    capture_thread.start()
    
    # Start Flask app
    try:
        app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        camera_ready = False
        if camera is not None:
            camera.release()
