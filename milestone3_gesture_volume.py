import cv2
import mediapipe as mp
import math
import time
import platform
from collections import deque
import threading

from flask import Flask, render_template, Response, jsonify

# ---------------- Flask App ----------------
app = Flask(__name__)

# ---------------- Global States ----------------
frame = None
current_volume = 0
current_status = "Waiting"
fps_value = 0

observed_min = 20
observed_max = 250
calibration_mode = None

# Detection toggle
DETECTION_ENABLED = True

# ---------------- Windows Volume ----------------
USE_WINDOWS_VOLUME = False
volume_interface = None

if platform.system() == "Windows":
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
        USE_WINDOWS_VOLUME = True
    except Exception:
        USE_WINDOWS_VOLUME = False

# ---------------- MediaPipe ----------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# ---------------- Helpers ----------------
def linear_map(x, in_min, in_max, out_min, out_max):
    if in_max == in_min:
        return out_min
    x = max(min(x, in_max), in_min)
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# ---------------- Camera ----------------
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

smooth_window = deque(maxlen=6)
last_set_percent = -1
last_set_time = 0

# ---------------- Gesture Loop ----------------
def gesture_loop():
    global frame, current_volume, current_status
    global last_set_percent, last_set_time
    global fps_value, observed_min, observed_max, calibration_mode
    global DETECTION_ENABLED

    prev_time = time.time()

    while True:
        ret, img = cap.read()
        if not ret:
            continue

        img = cv2.flip(img, 1)
        h, w, _ = img.shape

        # FPS
        curr_time = time.time()
        fps_value = int(1 / (curr_time - prev_time + 1e-6))
        prev_time = curr_time

        # Detection paused
        if not DETECTION_ENABLED:
            current_status = "Detection Paused"
            cv2.putText(img, "DETECTION PAUSED", (160, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 0, 255), 3)
            frame = img
            continue

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        current_status = "No Hand"

        if res.multi_hand_landmarks:
            hand = res.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(img, hand, mp_hands.HAND_CONNECTIONS)

            lm = hand.landmark
            x1, y1 = int(lm[4].x * w), int(lm[4].y * h)
            x2, y2 = int(lm[8].x * w), int(lm[8].y * h)

            distance = math.hypot(x2 - x1, y2 - y1)

            if calibration_mode == "min":
                observed_min = distance
                calibration_mode = None
            elif calibration_mode == "max":
                observed_max = distance
                calibration_mode = None

            vol_percent = linear_map(distance, observed_min, observed_max, 0, 100)
            vol_percent = int(max(0, min(100, vol_percent)))

            smooth_window.append(vol_percent)
            smooth_percent = int(sum(smooth_window) / len(smooth_window))

            current_volume = smooth_percent
            current_status = "Hand Detected"

            now = time.time()
            if USE_WINDOWS_VOLUME:
                if abs(smooth_percent - last_set_percent) >= 2 and (now - last_set_time) > 0.12:
                    try:
                        volume_interface.SetMasterVolumeLevelScalar(
                            smooth_percent / 100.0, None
                        )
                        last_set_percent = smooth_percent
                        last_set_time = now
                    except Exception:
                        pass

        cv2.putText(img, f'Volume: {current_volume}%', (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(img, f'FPS: {fps_value}', (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        frame = img

# ---------------- Video Stream ----------------
def generate_frames():
    global frame
    while True:
        if frame is None:
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() + b'\r\n')

# ---------------- Flask Routes ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({
        "volume": current_volume,
        "status": current_status,
        "fps": fps_value,
        "enabled": DETECTION_ENABLED
    })

@app.route('/toggle_detection', methods=['POST'])
def toggle_detection():
    global DETECTION_ENABLED
    DETECTION_ENABLED = not DETECTION_ENABLED
    return jsonify({"enabled": DETECTION_ENABLED})

@app.route('/calibrate/min', methods=['POST'])
def calibrate_min():
    global calibration_mode
    calibration_mode = "min"
    return jsonify({"message": "MIN calibration set"})

@app.route('/calibrate/max', methods=['POST'])
def calibrate_max():
    global calibration_mode
    calibration_mode = "max"
    return jsonify({"message": "MAX calibration set"})

# ---------------- Run ----------------
if __name__ == "__main__":
    t = threading.Thread(target=gesture_loop)
    t.daemon = True
    t.start()

    app.run(debug=False)

    cap.release()
    cv2.destroyAllWindows()
