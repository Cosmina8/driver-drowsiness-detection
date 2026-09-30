import subprocess
import time
import signal
import os
import cv2
import numpy as np
import dlib
from flask import Flask, Response
from gps_reader import GPSReader
from notifier import send_whatsapp_alert
from logger_alerts import log_alert
from config import (
    WHATSAPP_COOLDOWN_SECONDS,
    LED_ALERT_GPIO,
    BUZZER_GPIO,
    LED_SYSTEM_GPIO,
    EAR_THRESHOLD,
    MAR_THRESHOLD,
    EYE_CLOSED_FRAMES,
    YAWN_FRAMES
)

app = Flask(__name__)

gps = GPSReader()
gps.start()

last_whatsapp_alert_time = 0

# =========================
# GPIO control cu gpioset
# =========================
GPIO_CHIP = "gpiochip0"
GPIO_PROC = None
GPIO_STATE = None  # "on" / "off" / None

def _stop_gpio_process():
    global GPIO_PROC
    if GPIO_PROC is not None and GPIO_PROC.poll() is None:
        GPIO_PROC.terminate()
        try:
            GPIO_PROC.wait(timeout=0.3)
        except subprocess.TimeoutExpired:
            GPIO_PROC.kill()
            try:
                GPIO_PROC.wait(timeout=0.3)
            except Exception:
                pass
    GPIO_PROC = None

def _start_gpio_hold(led_value: int, buz_value: int):
    global GPIO_PROC
    GPIO_PROC = subprocess.Popen(
        [
            "gpioset",
            "--chip",
            GPIO_CHIP,
            f"17={led_value}",
            f"18={buz_value}",
            "27=1"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def set_alert_state(on: bool):
    global GPIO_STATE

    desired = "on" if on else "off"
    if GPIO_STATE == desired:
        return

    _stop_gpio_process()
    time.sleep(0.05)

    if on:
        _start_gpio_hold(1, 1)
    else:
        _start_gpio_hold(0, 0)

    GPIO_STATE = desired


def force_gpio_off():
    global GPIO_STATE
    GPIO_STATE = None

    try:
        _stop_gpio_process()
    except Exception:
        pass

    try:
        p = subprocess.Popen(
            ["gpioset", "--chip", GPIO_CHIP, "17=0", "18=0", "27=0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.2)
        if p.poll() is None:
            p.terminate()
    except Exception:
        pass


def handle_exit(sig, frame):
    print("\nOprire manuala...")
    force_gpio_off()
    print("GPIO oprit: LED rosu, buzzer, LED verde.")
    os._exit(0)

# =========================
# Camera MJPEG settings
# =========================
W, H = 480, 360
FRAMERATE = 20
JPEG_QUALITY = 60

# =========================
# Dlib
# =========================
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

LEFT_EYE_IDX = list(range(36, 42))
RIGHT_EYE_IDX = list(range(42, 48))
OUTER_MOUTH_IDX = list(range(48, 60))

def dist(p, q):
    return float(np.linalg.norm(np.array(p) - np.array(q)))

def ear_from_6pts(pts):
    p1, p2, p3, p4, p5, p6 = pts
    return (dist(p2, p6) + dist(p3, p5)) / (2.0 * dist(p1, p4) + 1e-6)

def mouth_aspect_ratio(pts):
    """
    MAR aproximativ folosind punctele gurii din modelul dlib 68:
    48..59 = contur exterior
    """
    p48 = pts[48]
    p50 = pts[50]
    p51 = pts[51]
    p53 = pts[53]
    p54 = pts[54]
    p57 = pts[57]
    p58 = pts[58]
    p59 = pts[59]

    A = dist(p51, p59)
    B = dist(p53, p57)
    C = dist(p50, p58)
    D = dist(p48, p54) + 1e-6

    return (A + B + C) / (2.0 * D)

def shape_to_np(shape):
    return [(shape.part(i).x, shape.part(i).y) for i in range(68)]

# =========================
# Fast MJPEG capture
# =========================
def mjpeg_stream_process():
    cmd = [
        "rpicam-vid",
        "-t", "0",
        "--width", str(W),
        "--height", str(H),
        "--framerate", str(FRAMERATE),
        "--codec", "mjpeg",
        "--quality", str(JPEG_QUALITY),
        "-n",
        "--inline",
        "--flush",
        "-o", "-"
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0
    )

def mjpeg_frames(proc):
    buf = b""
    while True:
        chunk = proc.stdout.read(4096)
        if not chunk:
            break

        buf += chunk
        a = buf.find(b"\xff\xd8")
        b = buf.find(b"\xff\xd9")

        if a != -1 and b != -1 and b > a:
            jpg = buf[a:b + 2]
            buf = buf[b + 2:]
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                yield img

# =========================
# Main generator
# =========================
def generate_frames():
    global last_whatsapp_alert_time
    # OCHI
    EAR_THRESH = EAR_THRESHOLD
    BLINK_MAX = 5
    DROWSY_N = EYE_CLOSED_FRAMES

    # GURĂ
    MAR_THRESH = MAR_THRESHOLD
    YAWN_N = YAWN_FRAMES

    closed_frames = 0
    yawn_frames = 0
    alarm_active = False
    gps_alert_sent = False
    last_gps_link = None

    prev = time.time()
    fps = 0.0

    proc = mjpeg_stream_process()

    set_alert_state(False)

    try:
        for img in mjpeg_frames(proc):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = detector(gray, 0)

            eye_status = "NU vad fata"
            mouth_status = ""
            ear_val = None
            mar_val = None

            drowsy_detected = False
            yawn_detected = False

            if len(faces) > 0:
                face = faces[0]

                x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

                shape = predictor(gray, face)
                pts = shape_to_np(shape)

                # OCHI
                left_eye = [pts[i] for i in LEFT_EYE_IDX]
                right_eye = [pts[i] for i in RIGHT_EYE_IDX]

                for p in left_eye + right_eye:
                    cv2.circle(img, p, 2, (0, 255, 255), -1)

                ear_left = ear_from_6pts(left_eye)
                ear_right = ear_from_6pts(right_eye)
                ear_val = (ear_left + ear_right) / 2.0

                if ear_val < EAR_THRESH:
                    closed_frames += 1
                else:
                    closed_frames = 0

                if 1 <= closed_frames <= BLINK_MAX:
                    eye_status = f"CLIPIRE ({closed_frames})"
                elif BLINK_MAX < closed_frames < DROWSY_N:
                    eye_status = f"OCHI INCHISI ({closed_frames})"
                elif closed_frames >= DROWSY_N:
                    eye_status = f"ALERTA OBOSEALA ({closed_frames})"
                    drowsy_detected = True
                    cv2.putText(
                        img,
                        "ALERTA: OBOSEALA!",
                        (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 0, 255),
                        3
                    )
                else:
                    eye_status = "OK OCHI"

                # GURĂ
                mouth_pts = [pts[i] for i in OUTER_MOUTH_IDX]

                for p in mouth_pts:
                    cv2.circle(img, p, 2, (255, 0, 0), -1)

                mar_val = mouth_aspect_ratio(pts)

                if mar_val > MAR_THRESH:
                    yawn_frames += 1
                else:
                    yawn_frames = 0

                if yawn_frames >= YAWN_N:
                    mouth_status = f"ALERTA CASCAT ({yawn_frames})"
                    yawn_detected = True
                    cv2.putText(
                        img,
                        "ALERTA: CASCAT!",
                        (20, 200),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 0, 255),
                        3
                    )
                else:
                    mouth_status = "OK GURA"

            else:
                closed_frames = 0
                yawn_frames = 0

            # ALERTĂ hardware dacă oricare din ele este activă
            if drowsy_detected or yawn_detected:
                if not alarm_active:
                    alarm_active = True
                    set_alert_state(True)

                if not gps_alert_sent:
                    location = gps.get_last_location()

                    if location:
                        maps_link = location["maps_link"]
                        last_gps_link = maps_link
                        

                        with open("alert_location.txt", "w", encoding="utf-8") as f:
                            f.write("ALERTĂ! Șoferul prezintă semne de oboseală.\n")
                            f.write(f"Data/Ora: {location['timestamp']}\n")
                            f.write(f"Latitudine: {location['lat']}\n")
                            f.write(f"Longitudine: {location['lon']}\n")
                            f.write(f"Locație Google Maps: {maps_link}\n")

                        print(f"Locație alertă: {maps_link}")
                        current_time = time.time()

                        if current_time - last_whatsapp_alert_time >= WHATSAPP_COOLDOWN_SECONDS:
                            whatsapp_sent = send_whatsapp_alert(location)
                            last_whatsapp_alert_time = current_time

                            if drowsy_detected and yawn_detected:
                                alert_type = "OBOSEALA + CASCAT"
                            elif drowsy_detected:
                                alert_type = "OBOSEALA"
                            elif yawn_detected:
                                alert_type = "CASCAT"
                            else:
                                alert_type = "NECUNOSCUT"

                            log_alert(alert_type, location, whatsapp_sent)

                        else:
                            print("[INFO] Cooldown activ - WhatsApp nu se retrimite și alerta nu se loghează repetat.")

                        gps_alert_sent = True  
                        
                    else:
                        print("Alertă detectată, dar încă nu există locație GPS validă.")

            else:
                if alarm_active:
                    alarm_active = False
                    set_alert_state(False)

                gps_alert_sent = False

            # FPS
            now = time.time()
            dt = now - prev
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)
            prev = now

            cv2.putText(
                img,
                f"FPS: {fps:.1f}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2
            )

            if ear_val is not None:
                cv2.putText(
                    img,
                    f"EAR: {ear_val:.3f}",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (255, 255, 0),
                    2
                )

            if mar_val is not None:
                cv2.putText(
                    img,
                    f"MAR: {mar_val:.3f}",
                    (20, 160),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (255, 200, 0),
                    2
                )

            cv2.putText(
                img,
                eye_status,
                (20, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2
            )

            if mouth_status:
                cv2.putText(
                    img,
                    mouth_status,
                    (20, 280),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (255, 255, 255),
                    2
                )

            ok, buffer = cv2.imencode(
                ".jpg",
                img,
                [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            )
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                buffer.tobytes() +
                b"\r\n"
            )

    finally:
        try:
            set_alert_state(False)
            subprocess.run(["gpioset", "--chip", GPIO_CHIP, "27=0"])
        except Exception:
            pass

        try:
            _stop_gpio_process()
        except Exception:
            pass

        try:
            proc.terminate()
        except Exception:
            pass

@app.route("/")
def index():
    return """
    <html>
    <head>
        <title>Sistem Detectare Oboseala Sofer</title>
        <style>
            body {
                background-color: #111;
                color: white;
                font-family: Arial;
                text-align: center;
            }
            h1 {
                color: #00ff88;
            }
            .status {
                margin: 20px;
                padding: 10px;
                background: #222;
                border-radius: 10px;
                display: inline-block;
            }
            img {
                border: 4px solid #00ff88;
                border-radius: 12px;
                margin-top: 20px;
                width: 640px;
            }
        </style>
    </head>
    <body>
        <h1>SISTEM INTELIGENT DE DETECTARE A OBOSELII ȘOFERULUI</h1>

        <div class="status">
            <h3>STATUS SISTEM: ACTIV</h3>
            <p>Monitorizare video în timp real</p>
            <p>WhatsApp Alert Activ</p>
            <p>GPS Tracking Activ</p>
        </div>

        <br>

        <img src="/video_feed">

    </body>
    </html>
    """

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("Server FATIGUE FULL pornit pe port 5002")
    try:
        app.run(host="0.0.0.0", port=5002, threaded=False, use_reloader=False)
    finally:
        force_gpio_off()
