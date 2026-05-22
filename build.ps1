# build.ps1 - Build Docker images for Smart Attendance Timetable

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Smart Attendance Timetable - Docker Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Initialize directories first
Write-Host "Initializing directories..." -ForegroundColor Yellow
& .\init-docker.ps1
Write-Host ""

$choice = Read-Host "What would you like to build?`n1. All services`n2. Facial Recognition only`n3. Timetable Maker only`nEnter choice (1-3)"

switch ($choice) {
    "1" {
        Write-Host "Building all Docker images..." -ForegroundColor Yellow
        docker-compose build
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Build completed successfully!" -ForegroundColor Green
        } else {
            Write-Host "✗ Build failed!" -ForegroundColor Red
            exit 1
        }
    }
    "2" {
        Write-Host "Building facial recognition image..." -ForegroundColor Yellow
        docker build -f Dockerfile.facial_recognition -t smart-facial-recognition .
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Facial recognition image built successfully!" -ForegroundColor Green
        } else {
            Write-Host "✗ Build failed!" -ForegroundColor Red
            exit 1
        }
    }
    "3" {
        Write-Host "Building timetable maker image..." -ForegroundColor Yellow
        docker build -f Dockerfile.timetable_maker -t smart-timetable-maker .
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Timetable maker image built successfully!" -ForegroundColor Green
        } else {
            Write-Host "✗ Build failed!" -ForegroundColor Red
            exit 1
        }
    }
    default {
        Write-Host "Invalid choice!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Build process completed!" -ForegroundColor Green
