# Real-Time Driver Drowsiness & Fatigue Detection System

An intelligent embedded Advanced Driver Assistance System (ADAS) designed to monitor driver alertness in real time using computer vision. Built on **Raspberry Pi 5**, the system detects fatigue and yawning, triggering local acoustic/visual warnings and automated remote emergency alerts via WhatsApp with real-time GPS coordinates.

---

## 📌 Features

- **Real-Time Facial Landmark Tracking:** Utilizes `dlib`'s 68-point facial landmark detector for eye and mouth tracking.
- **Drowsiness & Microsleep Detection:** Calculates **Eye Aspect Ratio (EAR)** to detect prolonged eye closure.
- **Yawn Detection:** Monitors **Mouth Aspect Ratio (MAR)** to identify frequent or continuous yawning.
- **Local Alerts:** Controls hardware indicators (Buzzer and LEDs via GPIO pins) for immediate in-cabin alerts.
- **Remote Emergency Notifications:** Dispatches automated WhatsApp alerts containing timestamped messages and Google Maps live location links using Green API.
- **Live Video Streaming:** Web-based live feed powered by Flask for real-time monitoring and debugging.

---

## 🛠️ Hardware & Software Stack

### Hardware
- **Single Board Computer:** Raspberry Pi 5
- **Camera:** IR-CUT Camera module (optimized for low-light/night driving)
- **Sensors & Peripherals:** GPS Module (NMEA communication), Active Buzzer, Alert LEDs

### Software & Libraries
- **Language:** Python 3.12+
- **Computer Vision:** OpenCV (`cv2`), `dlib`
- **Data & Math:** `numpy`
- **Embedded Control:** `gpiod` / Raspberry Pi GPIO
- **Web & Messaging:** Flask, Requests, Green API (WhatsApp Gateway)

---

## 📐 How It Works

1. **Face & Landmark Detection:** Each video frame is captured and converted to grayscale. The face is detected and 68 landmark points are mapped.
2. **Metric Evaluation:**
   - **EAR (Eye Aspect Ratio):** Monitored against predefined thresholds (`EAR_THRESHOLD`). If EAR falls below the threshold for a set number of consecutive frames (`EYE_CLOSED_FRAMES`), drowsiness is confirmed.
   - **MAR (Mouth Aspect Ratio):** Monitored against `MAR_THRESHOLD`. Sustained high MAR triggers yawn counters (`YAWN_FRAMES`).
3. **Alert Dispatch:**
   - **Local:** Immediate buzzer tone and alert LED trigger.
   - **Remote:** GPS coordinates (`lat`, `lon`) are retrieved via `gps_reader.py` and transmitted via WhatsApp to designated emergency contacts.

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone [https://github.com/Cosmina8/driver-drowsiness-detection.git](https://github.com/Cosmina8/driver-drowsiness-detection.git)
cd driver-drowsiness-detection
```

### 2. Download dlib Pre-trained Model
Download the 68-point facial landmark model into the project directory:
```bash
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bzip2 -d shape_predictor_68_face_landmarks.dat.bz2
```

### 3. Configure Credentials
Update `config.py` with your Green API credentials and emergency contacts:
```python
ID_INSTANCE = "YOUR_INSTANCE_ID"
API_TOKEN_INSTANCE = "YOUR_API_TOKEN"
WHATSAPP_CONTACTS = ["407XXXXXXXX"]
```

### 4. Run the System
```bash
python3 stream_fatigue_full.py
```
Access the local video stream in your browser at `http://<raspberry-pi-ip>:5000`.