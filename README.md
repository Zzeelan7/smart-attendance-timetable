# Smart Attendance & Timetable System

A mini-project combining **AI-based Facial Recognition Attendance** and a **Smart Constraint-based Timetable Generator**, built with Python and Flask.

---

## 📦 Modules

### 1. Facial Recognition Attendance System (`/facial_recognition`)
- Register student faces via webcam
- Mark attendance automatically by detecting and matching faces in real time
- View and export attendance reports (CSV)
- Built with: `OpenCV`, `face_recognition` (dlib), `Flask`

### 2. Smart Timetable Generator (`/timetable_maker`)
- 3-step wizard: upload student list → assign teachers → generate
- Constraint-based scheduler (C1: max 2 first-period classes, C2: at least 1 third-period class, C3: even workload distribution)
- Auto-splits students into sections (≤ 75 per section, equal strength)
- View timetables by Section A, Section B, Teacher, or Student
- Export as **Excel (.xlsx)** or **PDF**
- Built with: `Flask`, `openpyxl`, `reportlab`

---

## 🚀 Running the System

### Option 1: Docker (Recommended) ⭐

Docker eliminates all dependency issues! Builds will work on any system.

#### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop)

#### Quick Start
```bash
# Build and start all services
docker-compose build
docker-compose up -d

# Access services
# Facial Recognition: http://localhost:5000
# Timetable Maker:    http://localhost:5001

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Windows Users:** Use the provided PowerShell scripts
```powershell
.\build.ps1      # Build images
.\run.ps1        # Manage services
```

📖 See [QUICKSTART.md](QUICKSTART.md) for detailed Docker instructions.

---

### Option 2: Local Installation

#### Prerequisites
- Python 3.9+
- pip
- CMake (required for dlib)
- Visual Studio Build Tools (Windows) or build-essential (Linux)

#### Facial Recognition
```bash
cd facial_recognition
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

> ⚠️ Requires webcam and `dlib` compilation. This often fails on Windows without proper build tools. Use Docker instead!

#### Timetable Generator
```bash
cd timetable_maker
pip install -r requirements.txt
python app.py
# Open http://localhost:5001
```

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Face Detection | OpenCV, face_recognition (dlib HOG) |
| Scheduling | Custom greedy constraint algorithm |
| Excel Export | openpyxl |
| PDF Export | ReportLab |
| Frontend | HTML, CSS, Vanilla JS |

## 📐 Hardware Integration (Planned)
- **ESP32-S3** — Main controller
- **ESP32-CAM** — Live video stream to facial recognition
- **R307S Optical Fingerprint Sensor** — Secondary biometric verification
- **ILI9341 2.4″ TFT Display** — Shows timetable and prompts
- **WhatsApp Chatbot (Twilio)** — Sends daily timetable to student

---

## 👥 Team
4th Semester ECE Mini Project
