# init-docker.ps1 - Initialize directories before Docker run

Write-Host "Initializing Docker directories..." -ForegroundColor Cyan

# Create necessary directories
$dirs = @(
    "./facial_recognition/known_faces",
    "./facial_recognition/data",
    "./facial_recognition/static",
    "./timetable_maker/output",
    "./timetable_maker/static"
)

foreach ($dir in $dirs) {
    if (-Not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✓ Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "✓ Exists: $dir" -ForegroundColor Gray
    }
}

# Create .env if it doesn't exist
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "✓ Created: .env (customize as needed)" -ForegroundColor Green
} else {
    Write-Host "✓ Exists: .env" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Initialization complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Run .\build.ps1 to build Docker images" -ForegroundColor Cyan
