@echo off
REM Start Windows Camera Server for Docker containers
REM This script captures your webcam and streams it to Docker via HTTP

echo.
echo =========================================
echo  Windows Camera Server for Docker
echo =========================================
echo.
echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install flask opencv-python requests -q

echo [3/3] Starting camera server on http://127.0.0.1:8765...
echo.
echo Camera will be available at: http://host.docker.internal:8765/stream
echo.
echo Keep this window open while using the facial recognition system.
echo Press Ctrl+C to stop the server.
echo.
python windows_camera_server.py --port 8765 --camera 0

pause
