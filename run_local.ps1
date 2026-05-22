# run_local.ps1 - Run Smart Attendance Timetable locally with Webcam support

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Smart Attendance Timetable - Local Run" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Stop conflicting Docker containers to release ports 5000 & 5001
Write-Host "Stopping Docker containers to free up ports..." -ForegroundColor Yellow
docker-compose down
Write-Host ""

# 2. Check if Python is installed
try {
    python --version | Out-Null
} catch {
    Write-Host "✗ Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.9+ and add it to your environment PATH variables." -ForegroundColor Yellow
    exit 1
}

# 3. Start local servers using run_all.py
Write-Host "Starting local servers (webcam support enabled)..." -ForegroundColor Yellow
python run_all.py
