# Docker Troubleshooting Guide

## The dlib CMake Issue - SOLVED by Docker ✓

### What Was the Problem?

You were getting:
```
CMake Error at CMakeLists.txt:14 (project):
  No CMAKE_C_COMPILER could be found.
```

**Why?**
- `face-recognition` requires `dlib`
- `dlib` needs to be compiled from source on Windows
- The C/C++ compiler wasn't found on your Windows system
- You'd need: Visual Studio Build Tools, CMake, and proper environment setup

**Docker Solution:**
- Uses a Linux container with all build tools pre-installed
- No compiler needed on your Windows machine
- `dlib` compiles instantly in the container

---

## Build Issues

### Issue: Build takes forever (first time)

**Expected behavior:** 
- First build: 5-10 minutes (compiling dlib)
- Subsequent builds: 1-2 minutes (Docker cache)

**What to do:**
- Let it finish - don't interrupt
- Check progress: `docker build -f Dockerfile.facial_recognition . --progress=plain`

---

### Issue: Build fails with "network error"

**Solution:**
```powershell
# Check internet connection
Test-NetConnection 8.8.8.8

# Retry build with timeout
docker-compose build --no-cache --timeout 600

# If still failing, manually pull base image first
docker pull python:3.11-slim
docker-compose build facial_recognition
```

---

### Issue: "not enough space" or "disk full"

**Check disk space:**
```powershell
Get-Volume | Where-Object {$_.FileSystem -eq "NTFS"} | Format-Table

# Clean up Docker
docker system prune -a --volumes
```

**Free up space:**
- Images: ~2GB (facial_recognition) + ~500MB (timetable_maker)
- Consider external SSD if low on space

---

## Runtime Issues

### Issue: Container exits immediately

**Check logs:**
```powershell
docker-compose logs facial_recognition
```

**Common causes:**
- Port already in use → Change port in docker-compose.yml
- Python error → Check app.py for syntax issues
- Missing data directory → Create `facial_recognition/data/`

**Fix data directory:**
```powershell
New-Item -Path "./facial_recognition/data" -ItemType Directory -Force
New-Item -Path "./facial_recognition/known_faces" -ItemType Directory -Force
docker-compose up -d
```

---

### Issue: "Port 5000 is already in use"

**Find what's using it:**
```powershell
# Show process using the port
netstat -ano | findstr ":5000"

# Result: TCP 127.0.0.1:5000 LISTENING 12345
# Process ID is 12345

# Kill the process
taskkill /PID 12345 /F

# Or change the port in docker-compose.yml
# ports:
#   - "5050:5000"  # Changed from 5000:5000
```

---

### Issue: Cannot access localhost:5000

**Check if container is running:**
```powershell
docker-compose ps
# Should show containers with "Up" status
```

**If not running, start it:**
```powershell
docker-compose up -d
```

**Check logs for errors:**
```powershell
docker-compose logs facial_recognition | Select-Object -Last 20
```

**Try accessing from inside container:**
```powershell
# Open shell in container
docker exec -it smart-facial-recognition bash

# Test if app is listening
curl http://localhost:5000

# If it works inside but not outside, it's a port mapping issue
```

---

### Issue: Webcam not working in container

**Windows/Docker Desktop:**
- Recent Docker Desktop versions support webcam access automatically
- Test by uploading an image instead

**Enable USB/device passthrough:**
```yaml
# docker-compose.yml
services:
  facial_recognition:
    devices:
      - /dev/video0:/dev/video0  # Linux only
```

**Windows workaround:**
- Use ESP32-CAM stream instead
- Set `CAMERA_SOURCE=http://192.168.x.x/stream` in `.env`

---

### Issue: Face recognition not working

**Check known_faces directory:**
```powershell
# Verify folder structure
Get-ChildItem ./facial_recognition/known_faces -Recurse

# Should look like:
# John_Doe/
#   ├── face1.jpg
#   └── face2.jpg
# Jane_Smith/
#   └── face1.jpg
```

**Rebuild encodings:**
```powershell
# Access container shell
docker exec -it smart-facial-recognition bash

# Rebuild
python -c "from recognition import FaceEngine; FaceEngine().rebuild_encodings()"

# Exit
exit
```

**Quality requirements for face images:**
- Clear, front-facing photos
- Good lighting (no shadows)
- Face occupies 50%+ of image
- Minimum 2-3 photos per person

---

### Issue: Timetable maker says "No wizard_state.json found"

**This is expected:**
- You need to generate a timetable first in the UI
- Or copy/move data from other sources

**Generate via UI:**
1. Go to http://localhost:5001
2. Follow the wizard
3. This creates wizard_state.json
4. Facial recognition system can then sync it

---

### Issue: Volumes not persisting (files disappear)

**Problem:** You used `docker-compose down -v`
- The `-v` flag deletes volumes
- Your data is gone

**Correct commands:**
```powershell
# Stop but keep data
docker-compose stop

# Stop and remove containers (keep volumes)
docker-compose down

# Stop, remove containers AND volumes (deletes data!)
docker-compose down -v  # Don't do this unless you mean it
```

**Prevent data loss:**
```powershell
# Backup your volumes before cleanup
Copy-Item "./facial_recognition/known_faces" "./facial_recognition/known_faces_backup" -Recurse
Copy-Item "./timetable_maker/output" "./timetable_maker/output_backup" -Recurse
```

---

### Issue: "error: failed-wheel-build-for-install"

**This was your original error!** Docker fixes this by providing proper build tools.

**If it happens in Docker:**
```powershell
# Full rebuild without cache
docker-compose build --no-cache facial_recognition

# If still fails, check base image
docker pull python:3.11-slim
docker-compose build --no-cache --timeout 600 facial_recognition
```

---

## Performance Optimization

### Docker is slow / using too much memory

**Check resource limits:**
```powershell
# View container stats in real-time
docker stats

# View one container
docker stats smart-facial-recognition
```

**Limit resources in docker-compose.yml:**
```yaml
services:
  facial_recognition:
    deploy:
      resources:
        limits:
          cpus: '2.0'           # Max 2 CPU cores
          memory: 2G            # Max 2GB RAM
        reservations:
          cpus: '1.0'           # Guaranteed 1 CPU
          memory: 1G            # Guaranteed 1GB RAM
```

---

### Slow file operations / recognition

**Check volume mount type:**
- Docker for Windows mounts Windows drives slowly
- Move project to WSL2 if possible: faster performance

**In docker-compose.yml:**
```yaml
volumes:
  # This is slow on Windows
  - ./facial_recognition/known_faces:/app/facial_recognition/known_faces

  # Faster: named volume
  - facial_faces:/app/facial_recognition/known_faces

volumes:
  facial_faces:
```

---

## Debugging

### Enable verbose logging

**In docker-compose.yml:**
```yaml
environment:
  - FLASK_DEBUG=True
  - PYTHONUNBUFFERED=1
```

**View detailed logs:**
```powershell
docker-compose logs -f --tail=100 facial_recognition
```

### Execute commands in container

```powershell
# Open bash shell
docker exec -it smart-facial-recognition bash

# Run Python interactively
docker exec -it smart-facial-recognition python

# Run specific command
docker exec smart-facial-recognition python -c "import cv2; print(cv2.__version__)"

# Exit bash
exit
```

---

## Network Issues

### Can't reach container from another machine

**Problem:** You used `localhost:5000` from another PC
- Containers are accessible only from localhost by default

**Solution 1 - Use machine IP:**
```
http://192.168.x.100:5000  # Instead of localhost:5000
```

Find your machine IP:
```powershell
ipconfig | Select-String "IPv4"
# Look for 192.168.x.x
```

**Solution 2 - Use reverse proxy (nginx):**
```yaml
# Add to docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - facial_recognition
      - timetable_maker
```

---

## Still Having Issues?

**Collect diagnostic info:**
```powershell
Write-Host "=== System Info ===" 
docker --version
docker-compose --version
(Get-WmiObject Win32_OperatingSystem).Caption

Write-Host "`n=== Container Status ===" 
docker-compose ps

Write-Host "`n=== Recent Logs ===" 
docker-compose logs --tail=50

Write-Host "`n=== Resource Usage ===" 
docker stats --no-stream
```

**Share this output when asking for help!**

---

## Complete Reset

**If everything is broken, nuclear option:**
```powershell
# Stop and remove everything
docker-compose down -v

# Remove images
docker rmi smart-facial-recognition smart-timetable-maker

# System cleanup
docker system prune -a --volumes

# Start fresh
docker-compose build --no-cache
docker-compose up -d
```

---

## Best Practices Going Forward

1. **Always backup data before cleanup:**
   ```powershell
   Copy-Item ./facial_recognition/known_faces ./backup -Recurse
   ```

2. **Use `.env` for configuration:**
   ```powershell
   # Copy template
   Copy-Item .env.example .env
   # Edit .env with your settings
   ```

3. **Check logs before restarting:**
   ```powershell
   docker-compose logs facial_recognition
   ```

4. **Use `docker-compose stop` instead of down:**
   - Keeps containers and data intact
   - Faster restart

5. **Keep Docker Desktop updated:**
   - Settings → Check for updates
   - Fixes many compatibility issues
