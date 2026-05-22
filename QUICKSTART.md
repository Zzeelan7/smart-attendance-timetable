# Quick Start Guide - Docker Setup

## Windows Users - Quick Start

### 1. Install Docker Desktop
- Download from [Docker Official Site](https://www.docker.com/products/docker-desktop)
- Install and restart your computer
- Verify: Open PowerShell and run:
  ```powershell
  docker --version
  docker-compose --version
  ```

### 2. Navigate to Project Directory
```powershell
cd C:\Users\zzeel\OneDrive\Desktop\smart_tt\smart-attendance-timetable
```

### 3. Build and Run Using PowerShell Scripts

**First Time Setup:**
```powershell
.\build.ps1
# Choose option 1 (All services)
```

**Start Services:**
```powershell
.\run.ps1
# Choose option 1 (Start in background) or 2 (Interactive logs)
```

### 4. Access Your Services
- **Facial Recognition**: http://localhost:5000
- **Timetable Maker**: http://localhost:5001

### 5. Stop Services
```powershell
.\run.ps1
# Choose option 3 (Stop all services)
```

---

## Alternative: Using Docker Compose Directly

```powershell
# Build
docker-compose build

# Start (background)
docker-compose up -d

# Start (interactive)
docker-compose up

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Show status
docker-compose ps
```

---

## Troubleshooting

### Issue: Docker is not running
**Solution**: 
- Open Docker Desktop application
- Wait for the "Docker Desktop is running" message

### Issue: Ports 5000 or 5001 are already in use
**Solution 1 - Change ports in docker-compose.yml:**
```yaml
ports:
  - "5000:5000"  # Change first 5000 to 5050 (or any free port)
```

**Solution 2 - Find what's using the port:**
```powershell
netstat -ano | findstr :5000
# This shows the Process ID (PID) using the port
taskkill /PID <PID> /F  # Force close it
```

### Issue: Build fails with "No CMAKE_C_COMPILER"
**This should be fixed by Docker!** Docker provides Linux environment with all build tools.

If it still fails:
```powershell
# Full rebuild without cache
docker-compose build --no-cache
```

### Issue: Permission denied when mounting volumes
**Solution** (Restart Docker):
```powershell
docker-compose down -v
docker-compose up --build
```

### Issue: Cannot connect to service at localhost
**For Linux/WSL2 users:**
- Use `localhost` or `127.0.0.1`
- If not working, find Docker's IP: `docker-machine ip` or use host IP

**For Windows (Docker Desktop):**
- Use `localhost` or `127.0.0.1` directly

### Issue: Out of disk space
```powershell
# Clean up unused images and containers
docker system prune -a

# Remove all stopped containers
docker container prune

# Remove all dangling images
docker image prune -a
```

---

## Next Steps

1. **Configure your environment** (Optional):
   - Copy `.env.example` to `.env`
   - Update values for your setup
   - Services will use `.env` automatically

2. **Upload known faces** for facial recognition:
   - Place face images in `facial_recognition/known_faces/`
   - Create folders named after each person
   - Restart the container to rebuild encodings

3. **Generate a timetable**:
   - Go to http://localhost:5001
   - Follow the wizard to create your timetable
   - It will be available to the facial recognition system

4. **Mark attendance**:
   - Go to http://localhost:5000
   - System will recognize and mark attendance for enrolled faces

---

## Performance Tips

- **First build takes 5-10 minutes** (especially facial_recognition with dlib)
- **Subsequent builds are much faster** (uses Docker cache)
- **CPU usage will spike during initial build**
- **Image size: ~2-3GB** for facial_recognition, ~500MB for timetable_maker

---

## Useful Commands

```powershell
# Execute command in running container
docker exec -it smart-facial-recognition bash

# View resource usage
docker stats

# Rebuild a specific service
docker-compose build facial_recognition

# Push to Docker Hub (if you tag it)
docker tag smart-facial-recognition:latest yourusername/smart-facial:latest
docker push yourusername/smart-facial:latest
```

---

## Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs -f facial_recognition`
2. Ensure Docker Desktop is fully updated
3. Try: `docker system prune -a` to clean up, then rebuild
4. Restart Docker Desktop: Quit and reopen the application

---

## When Done

To completely remove everything (including data):
```powershell
docker-compose down -v
docker rmi smart-facial-recognition smart-timetable-maker
```

To just stop but keep data:
```powershell
docker-compose stop
```

To restart existing containers:
```powershell
docker-compose start
```
