# run.ps1 - Run Smart Attendance Timetable services with Docker

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Smart Attendance Timetable - Docker Run" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Initialize directories first
Write-Host "Initializing directories..." -ForegroundColor Yellow
& .\init-docker.ps1
Write-Host ""
Write-Host "Checking Docker daemon..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
} catch {
    Write-Host "✗ Docker is not running! Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Docker is running" -ForegroundColor Green
Write-Host ""

$choice = Read-Host "What would you like to do?`n1. Start all services (background)`n2. Start all services (interactive logs)`n3. Stop all services`n4. Show service status`n5. Show logs`nEnter choice (1-5)"

switch ($choice) {
    "1" {
        Write-Host "Starting all services in background..." -ForegroundColor Yellow
        docker-compose up -d
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Services started successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Access endpoints:" -ForegroundColor Cyan
            Write-Host "  Facial Recognition: http://localhost:5000" -ForegroundColor White
            Write-Host "  Timetable Maker:    http://localhost:5001" -ForegroundColor White
            Write-Host ""
            Write-Host "View logs with: .\run.ps1 -choice 5" -ForegroundColor Gray
        } else {
            Write-Host "✗ Failed to start services!" -ForegroundColor Red
            exit 1
        }
    }
    "2" {
        Write-Host "Starting all services with interactive logs..." -ForegroundColor Yellow
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
        docker-compose up
    }
    "3" {
        Write-Host "Stopping all services..." -ForegroundColor Yellow
        docker-compose down
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Services stopped successfully!" -ForegroundColor Green
        } else {
            Write-Host "✗ Failed to stop services!" -ForegroundColor Red
            exit 1
        }
    }
    "4" {
        Write-Host "Service Status:" -ForegroundColor Cyan
        docker-compose ps
    }
    "5" {
        Write-Host "Showing logs (Press Ctrl+C to exit)..." -ForegroundColor Yellow
        Write-Host ""
        docker-compose logs -f
    }
    default {
        Write-Host "Invalid choice!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Operation completed!" -ForegroundColor Green
