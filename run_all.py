"""
run_all.py — Single launcher for the combined Smart Attendance + Timetable System.

Run this ONE file to start both modules:
    python run_all.py

Access the system at:
    http://localhost:5000
"""

import os
import sys
import threading
import webbrowser
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Start Facial Recognition (port 5000) ────────────────────────────
def start_facial_recognition():
    fr_dir = os.path.join(BASE_DIR, 'facial_recognition')
    sys.path.insert(0, fr_dir)
    os.chdir(fr_dir)
    try:
        import app as fr_app
        fr_app.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f'[Facial Recognition] Failed to start: {e}')
    finally:
        os.chdir(BASE_DIR)

# ── Start Timetable Maker (port 5001) ───────────────────────────────
def start_timetable_maker():
    tt_dir = os.path.join(BASE_DIR, 'timetable_maker')
    sys.path.insert(0, tt_dir)
    try:
        # Change to timetable dir so relative paths in app.py resolve correctly
        old_cwd = os.getcwd()
        os.chdir(tt_dir)
        import importlib, types

        # Load timetable app module cleanly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'timetable_app',
            os.path.join(tt_dir, 'app.py')
        )
        tt_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tt_mod)
        tt_mod.app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
    except Exception as e:
        print(f'[Timetable Maker] Failed to start: {e}')
    finally:
        os.chdir(BASE_DIR)

# ── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print()
    print('=' * 54)
    print('  Smart Attendance & Timetable System')
    print('=' * 54)
    print('  Facial Recognition  ->  http://localhost:5000')
    print('  Timetable Generator ->  http://localhost:5001')
    print('=' * 54)
    print('  Press Ctrl+C to stop both servers')
    print()

    # Start both in background threads
    t1 = threading.Thread(target=start_facial_recognition, daemon=True)
    t2 = threading.Thread(target=start_timetable_maker,    daemon=True)

    t1.start()
    time.sleep(1)   # slight delay so ports don't collide on startup
    t2.start()

    # Open browser to timetable maker (main entry point)
    time.sleep(2)
    webbrowser.open('http://localhost:5001')

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n  Shutting down both servers...')
