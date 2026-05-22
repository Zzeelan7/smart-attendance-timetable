# Docker Setup Guide for Smart Attendance Timetable

## Prerequisites

Before you begin, make sure you have Docker and Docker Compose installed:

- **Docker**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Docker Compose**: Usually comes with Docker Desktop

Verify installation:
```bash
docker --version
docker-compose --version
```

## Quick Start

### 1. Build and Run All Services

```bash
# Build the images
docker-compose build

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 2. Access the Services

- **Facial Recognition**: http://localhost:5000
- **Timetable Maker**: http://localhost:5001

### 3. View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f facial_recognition
docker-compose logs -f timetable_maker

# View last 50 lines
docker-compose logs --tail=50
```

### 4. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears persistent data)
docker-compose down -v

# Stop services but keep containers
docker-compose stop

# Restart services
docker-compose restart
```

## Building Individual Images

```bash
# Build only facial recognition
docker build -f Dockerfile.facial_recognition -t smart-facial-recognition .

# Build only timetable maker
docker build -f Dockerfile.timetable_maker -t smart-timetable-maker .
```

## Running Individual Containers

```bash
# Run facial recognition directly
docker run -it -p 5000:5000 \
  -v $(pwd)/facial_recognition/known_faces:/app/facial_recognition/known_faces \
  smart-facial-recognition

# Run timetable maker directly
docker run -it -p 5001:5001 \
  -v $(pwd)/timetable_maker/output:/app/timetable_maker/output \
  smart-timetable-maker
```

## Troubleshooting

### Port Already in Use

If ports 5000 or 5001 are already in use, modify the ports in `docker-compose.yml`:

```yaml
services:
  facial_recognition:
    ports:
      - "5000:5000"  # Change first number to an available port
```

### Container Won't Start

Check the logs:
```bash
docker-compose logs facial_recognition
```

### Building Takes Too Long

First build will take longer. Subsequent builds use cache:
```bash
# Force rebuild without cache
docker-compose build --no-cache
```

### Webcam Access (Linux/Mac only)

Uncomment the devices section in `docker-compose.yml`:

```yaml
services:
  facial_recognition:
    devices:
      - /dev/video0:/dev/video0
```

Windows users: Docker Desktop can access webcams directly in recent versions.

## Production Considerations

1. **Use specific base image versions**: Replace `python:3.11-slim` with `python:3.11.7-slim` for reproducibility
2. **Set FLASK_ENV to production**: Change `development` to `production`
3. **Use environment files**: Create `.env` file for sensitive configuration
4. **Add reverse proxy**: Use nginx for SSL and load balancing
5. **Volume backups**: Regularly backup `known_faces` and `output` directories

## Environment Variables

Create a `.env` file in the project root:

```env
# Flask Configuration
FLASK_ENV=production
DEBUG=false

# Facial Recognition
CAMERA_SOURCE=0
RECOGNITION_CONFIDENCE=0.6

# Timetable Maker
SEMESTER_DEFAULT=4
```

Reference in `docker-compose.yml`:
```yaml
services:
  facial_recognition:
    env_file: .env
```

## Database Integration (Future)

When adding database support, update docker-compose.yml:

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: smart_tt
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - smart-network

volumes:
  postgres_data:
```

## Useful Commands

```bash
# Rebuild a specific service
docker-compose build facial_recognition

# Scale a service (doesn't work well with Flask unless behind load balancer)
docker-compose up -d --scale facial_recognition=2

# Execute command in running container
docker exec -it smart-facial-recognition bash

# Monitor resource usage
docker stats

# Remove all unused images/containers
docker system prune -a
```

## Tips & Best Practices

- Keep Docker images small: Use `-slim` and `-alpine` variants
- Use `.dockerignore` to exclude unnecessary files
- Health checks help orchestration tools restart unhealthy containers
- Mount volumes for persistent data that should survive container restarts
- Use networks to enable inter-service communication
- Always tag images with versions in production
