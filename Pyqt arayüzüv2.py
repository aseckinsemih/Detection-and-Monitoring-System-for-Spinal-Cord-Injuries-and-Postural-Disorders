import sys
import json
import numpy as np
import cv2
import math
import base64
import requests
import webbrowser
import traceback
from scipy.interpolate import splprep, splev
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import time

# PyQt6 & PyQtGraph
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QScrollArea,
                             QStackedWidget, QFrame, QLineEdit, QSizePolicy)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QEvent, QMutex, QMutexLocker
from PyQt6.QtGui import QImage, QPixmap, QFont
import pyqtgraph as pg
import websocket

# =================================================================================
# --- SISTEM KONFIGURASYONU ---
# =================================================================================
ESP32_IP = "10.158.24.15"                            # Donanım IP (Lokal)
FASTAPI_URL = "http://127.0.0.1:8000/api/telemetry" # Onur'un Bulut Adresi (Docker)
SAM_API_URL = "https://sizin-sam-api-sunucunuz.com/segment" # SAM Sunucu Adresi

IMU_COUNT = 7
LEFT_STRIP_COUNT = 5
RIGHT_POINT_COUNT = 9
SEGMENT_LENGTH = 0.6

# =================================================================================
# Removed SpineAnalyzerSAM (Replaced with Pure MediaPipe Asymmetry)

# =================================================================================
# PART 2: ARKA PLAN ISCILERI (BULUT VE DONANIM)
# =================================================================================
class CloudUploaderWorker(QThread):
    """
    Persistent queue-based cloud uploader.
    Maintains a single running background thread to prevent thread thrashing and GUI lag.
    """
    status_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._queue = None
        self._mutex = QMutex()
        self._running = True

    def send_data(self, payload):
        with QMutexLocker(self._mutex):
            self._queue = payload  # Overwrite with the latest state payload

    def run(self):
        while self._running:
            payload = None
            with QMutexLocker(self._mutex):
                if self._queue is not None:
                    payload, self._queue = self._queue, None

            if payload is not None:
                try:
                    res = requests.post(FASTAPI_URL, json=payload, timeout=5)
                    if res.ok:
                        self.status_sig.emit("🟢 BULUT SENKRONIZASYONU AKTIF")
                    else:
                        self.status_sig.emit(f"🟡 BULUT HATASI: {res.status_code}")
                except requests.exceptions.RequestException:
                    self.status_sig.emit("🔴 BULUT SUNUCUSUNA ULASILAMIYOR")
                    # Silenced verbose printing to prevent console-buffer lag
            
            QThread.msleep(100)  # Check queue at 10Hz without CPU spinning

    def stop(self):
        self._running = False
        self.wait(2000)


class TelemetryWorker(QThread):
    data_signal = pyqtSignal(tuple)
    status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.url = f"ws://{ESP32_IP}:81"

    def run(self):
        while self.running:
            try:
                self.status_signal.emit("CONNECTING...")
                ws = websocket.WebSocket()
                ws.connect(self.url, timeout=2)
                self.status_signal.emit("LIVE")
                while self.running:
                    try:
                        msg = ws.recv()
                        if msg:
                            self.parse(msg)
                        else:
                            # Yield CPU execution to prevent a 100% core spinning tight loop if msg is empty
                            QThread.msleep(10)
                    except (websocket.WebSocketTimeoutException, TimeoutError):
                        # Gelen veri yok (Mega bagli olmayabilir) ama baglanti hala aktif
                        continue
            except Exception as e:
                print(f"[WS] {e}")
                self.status_signal.emit("OFFLINE")
                QThread.sleep(1)

    def parse(self, raw):
        try:
            raw = raw.strip()
            if not raw.startswith('{'):
                return

            p = json.loads(raw)

            # 1. Parse FSR sensors (5 values)
            fsr_list = p.get("fsr_sensors", [])
            fsr = [0.0] * LEFT_STRIP_COUNT
            for i, item in enumerate(fsr_list):
                if i < LEFT_STRIP_COUNT:
                    fsr[i] = list(item.values())[0] if item else 0.0

            # 2. Parse Nokta (pressure point) sensors (9 values)
            nok_list = p.get("nokta_sensors", [])
            nok = [0.0] * RIGHT_POINT_COUNT
            for i, item in enumerate(nok_list):
                if i < RIGHT_POINT_COUNT:
                    nok[i] = list(item.values())[0] if item else 0.0

            # 3. Parse and reconstruct IMU data (7 values: 5 active, 2 interpolated)
            pitch_roll = p.get("pitch_roll", [])
            pr_map = {}
            for item in pitch_roll:
                pos = item.get("pos")
                pitch = item.get("pitch", 0.0)
                roll = item.get("roll", 0.0)
                pr_map[pos] = (pitch, roll)

            ol_p, ol_r = pr_map.get("O_L", (0.0, 0.0))
            or_p, or_r = pr_map.get("O_R", (0.0, 0.0))
            s4_p, s4_r = pr_map.get("S4_top", (0.0, 0.0))
            s5_p, s5_r = pr_map.get("S5_mid", (0.0, 0.0))
            s1_p, s1_r = pr_map.get("S1_low", (0.0, 0.0))

            # S2 omurganın alt-orta bölgesinde: S1_low ile S5_mid arası %50
            s2_p = s1_p + 0.5 * (s5_p - s1_p)
            s2_r = s1_r + 0.5 * (s5_r - s1_r)

            # S3 omurganın orta bölgesinde: S5_mid'in hemen altında
            s3_p = s1_p + 0.75 * (s5_p - s1_p)
            s3_r = s1_r + 0.75 * (s5_r - s1_r)

            imus = [
                (ol_p, ol_r),  # 0: O_L
                (or_p, or_r),  # 1: O_R
                (s1_p, s1_r),  # 2: S1_low (alt bel)
                (s2_p, s2_r),  # 3: S2 (interpolated)
                (s3_p, s3_r),  # 4: S3 (interpolated)
                (s5_p, s5_r),  # 5: S5_mid (orta sırt)
                (s4_p, s4_r)   # 6: S4_top (boyun altı = en üst)
            ]

            l_arr = np.array(fsr, dtype=float).reshape(1, LEFT_STRIP_COUNT)
            r_arr = np.array(nok, dtype=float).reshape(3, 3)

            self.data_signal.emit((imus, l_arr, r_arr))
        except json.JSONDecodeError as e:
            print(f"[PARSE] JSON hatasi: {e} | raw={raw[:80]}")
        except Exception as e:
            print(f"[PARSE] {e}")
            traceback.print_exc()

    def stop(self):
        self.running = False
        self.wait(2000)

# =================================================================================
# PART 3: V27 MASTER CONSOLE (PYQT6 MAIN UI)
# =================================================================================
class ScoliosisMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clinical Platform")
        self.resize(1600, 950)
        self.setStyleSheet("background-color: #121212; color: white; font-family: Arial;")

        # Global Veri Depoları
        self.c_asym = 0.0
        self.c_spine = [0.0] * 5
        self.c_fsr_l = [0.0] * LEFT_STRIP_COUNT
        self.c_fsr_r = [0.0] * RIGHT_POINT_COUNT

        # Kamera Açı Depoları
        self.c_shoulder_tilt = 0.0
        self.c_pelvic_tilt = 0.0
        self.c_fhp = 0.0
        self.c_trunk_lean = 0.0
        self.c_face_lean = 0.0

        # Signal Processing States (FSR & IMU)
        self.fsr_l_ema = None
        self.fsr_r_ema = None
        self.imu_baseline = None
        self.latest_raw_imus = None
        self.USE_PITCH = False  # Set to True if you want to use Pitch instead of Roll for Spline
        self.FSR_GAIN = 15.0    # Gain multiplier to boost tiny FSR PSI values (0.04 -> 0.6)

        # Multi-Planar Modes
        self.current_mode = "CORONAL"  # CORONAL or SAGITTAL
        
        # MediaPipe Tasks API Başlatma (LIVE_STREAM Modu)
        base_options = mp_python.BaseOptions(model_asset_path='pose_landmarker.task')
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            result_callback=self.mp_callback,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.pose_tracker = vision.PoseLandmarker.create_from_options(options)
        self.latest_result = None
        self.latest_landmarks = None
        self.is_processing = False  # Asenkron AI kuyruk patlamasını önlemek için

        # Kamera Durumları
        self.cap = None
        self.cam_timer = QTimer()
        self.cam_timer.timeout.connect(self.update_cam)
        self.current_frame_cv = None
        self.lm_ema = {}  # MediaPipe Landmark EMA filtresi için
        self.mp_timestamp = 0  # Stabil tracking için yapay timestamp

        self.init_ui()
        
        # Sistemleri Bağla (Kritik: Callback içinde olmamalı)
        self.telemetry = TelemetryWorker()
        self.telemetry.data_signal.connect(self.update_telemetry)
        self.telemetry.status_signal.connect(self.update_hw_stat)

        self.cloud = CloudUploaderWorker()
        self.cloud.status_sig.connect(lambda s: self.lbl_cloud.setText(s))
        self.cloud.start()

        self.cloud_timer = QTimer()
        self.cloud_timer.timeout.connect(self.trigger_cloud)
        self.cloud_timer.start(1000)  # 1Hz Cloud Sync

    def mp_callback(self, result, output_image, timestamp_ms):
        # Arka planda asenkron olarak MediaPipe'tan dönen sonuçları kaydet
        self.latest_result = result
        self.is_processing = False  # AI boşa çıktı, yeni kare alabilir

    def init_ui(self):
        main_w = QWidget()
        self.setCentralWidget(main_w)
        layout = QHBoxLayout(main_w)
        layout.setContentsMargins(0, 0, 0, 0)

        # === SIDEBAR ===
        side = QFrame()
        side.setFixedWidth(280)
        side.setStyleSheet("background-color: #1E1E1E;")
        s_lay = QVBoxLayout(side)

        t = QLabel("CONTROL CENTER")
        t.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s_lay.addWidget(t)
        s_lay.addSpacing(20)

        self.b_home = self.c_btn("📊 CORSET ", lambda: self.stack.setCurrentIndex(0), "#1f538d")
        self.b_cam = self.c_btn("👁️ ASYMMETRY VISION", lambda: self.stack.setCurrentIndex(1), "#3b3b3b")
        s_lay.addWidget(self.b_home)
        s_lay.addWidget(self.b_cam)
        s_lay.addSpacing(10)

        self.b_db = self.c_btn("📂 ARCHIVE SYSTEM", self.route_db, "#4527A0")
        s_lay.addWidget(self.b_db)
        s_lay.addSpacing(20)

        # MODE SELECTION
        mod_lbl = QLabel("👁️ ANALYSIS MODE")
        mod_lbl.setStyleSheet("color: #00FFCC; font-weight: bold; font-size: 11px;")
        s_lay.addWidget(mod_lbl)
        
        self.b_mod_cor = self.c_btn("POSTERIOR (SCOLIOSIS)", lambda: self.set_mode("CORONAL"), "#555555")
        self.b_mod_sag = self.c_btn("LATERAL (KYPHOSIS)", lambda: self.set_mode("SAGITTAL"), "#222222")
        s_lay.addWidget(self.b_mod_cor)
        s_lay.addWidget(self.b_mod_sag)
        s_lay.addSpacing(15)

        # CONFIGURATION FIELDS
        cfg_lbl = QLabel("🔌 CONNECTION SETTINGS")
        cfg_lbl.setStyleSheet("color: #00FFCC; font-weight: bold; font-size: 11px;")
        s_lay.addWidget(cfg_lbl)

        # ESP32 IP Config
        ip_lay = QHBoxLayout()
        ip_lbl = QLabel("ESP32 IP:")
        ip_lbl.setStyleSheet("font-size: 11px; color: #bbb;")
        self.ip_input = QLineEdit(ESP32_IP)
        self.ip_input.setStyleSheet("background-color: #2b2b2b; color: white; border: 1px solid #444; border-radius: 4px; padding: 4px; font-size: 11px;")
        ip_lay.addWidget(ip_lbl)
        ip_lay.addWidget(self.ip_input)
        s_lay.addLayout(ip_lay)

        # Camera Index Config
        cam_lay = QHBoxLayout()
        cam_lbl = QLabel("CAM INDEX:")
        cam_lbl.setStyleSheet("font-size: 11px; color: #bbb;")
        self.cam_input = QLineEdit("0")
        self.cam_input.setStyleSheet("background-color: #2b2b2b; color: white; border: 1px solid #444; border-radius: 4px; padding: 4px; font-size: 11px;")
        cam_lay.addWidget(cam_lbl)
        cam_lay.addWidget(self.cam_input)
        s_lay.addLayout(cam_lay)
        s_lay.addSpacing(10)

        self.b_con = self.c_btn("▶ CONNECT HARDWARE", self.start_hw, "#2E7D32")
        self.b_dis = self.c_btn("■ DISCONNECT", self.stop_hw, "#C62828")
        self.b_dis.setEnabled(False)
        self.b_cal = self.c_btn("🎯 CALIBRATE IMU", self.calibrate_imu, "#FF8C00")
        s_lay.addWidget(self.b_con)
        s_lay.addWidget(self.b_dis)
        s_lay.addWidget(self.b_cal)

        df = QFrame()
        df.setStyleSheet("background-color: #121212; border-radius: 5px;")
        dl = QVBoxLayout(df)
        self.l_imu = QLabel("● IMU: WAIT")
        self.l_imu.setStyleSheet("color: gray;")
        self.l_fsr = QLabel("● FSR: WAIT")
        self.l_fsr.setStyleSheet("color: gray;")
        dl.addWidget(self.l_imu)
        dl.addWidget(self.l_fsr)
        s_lay.addWidget(df)
        s_lay.addStretch()

        self.lbl_cloud = QLabel("☁️ CLOUD: WAITING")
        self.lbl_cloud.setStyleSheet("color: gray; font-weight: bold;")
        self.l_stat = QLabel("● SYSTEM READY")
        self.l_stat.setStyleSheet("color: #00FFCC; font-weight: bold;")
        s_lay.addWidget(self.lbl_cloud)
        s_lay.addSpacing(10)
        s_lay.addWidget(self.l_stat)

        # === STACK ===
        self.stack = QStackedWidget()

        # PAGE 1: TELEMETRY
        p1 = QWidget()
        l1 = QHBoxLayout(p1)
        scr = QScrollArea()
        scr.setFixedWidth(250)
        scr.setStyleSheet("background-color: #1A1A1A; border: none;")
        sc_w = QWidget()
        sl = QVBoxLayout(sc_w)
        self.lbl_imus = [QLabel(f"IMU {i+1}: --") for i in range(IMU_COUNT)]
        for l in self.lbl_imus:
            l.setFont(QFont("Consolas", 10))
            sl.addWidget(l)

        sl.addSpacing(15)
        pt = QLabel("--- PRESSURE ---")
        pt.setStyleSheet("color: #55FFFF; font-weight: bold;")
        sl.addWidget(pt)
        self.lbl_l = [QLabel(f"STRIP {i+1}: --") for i in range(LEFT_STRIP_COUNT)]
        self.lbl_r = [QLabel(f"POINT {i+1}: --") for i in range(RIGHT_POINT_COUNT)]
        for l in self.lbl_l + self.lbl_r:
            sl.addWidget(l)
        sl.addStretch()
        scr.setWidget(sc_w)

        self.plot_s = pg.PlotWidget(title="CORONAL SCOLIOSIS")
        self.plot_s.setBackground('#1A1A1A')
        self.plot_s.setXRange(-2, 2)
        self.plot_s.setYRange(0, 5)
        self.crv = self.plot_s.plot(pen=pg.mkPen('#55FF55', width=5))
        self.pts = self.plot_s.plot(pen=None, symbol='o', symbolBrush='w', symbolSize=12)

        # 1. Left FSR Strip Plot
        self.plot_h1 = pg.PlotWidget(title="PRESSURE STRIP (LEFT)")
        self.plot_h1.setBackground('#1A1A1A')
        self.plot_h1.invertY(True)
        self.plot_h1.setAspectLocked(True)
        self.plot_h1.setXRange(0, 20)
        self.plot_h1.setYRange(100, 0)
        
        # 2. Right FSR Matrix Plot
        self.plot_h2 = pg.PlotWidget(title="PRESSURE MATRIX (RIGHT)")
        self.plot_h2.setBackground('#1A1A1A')
        self.plot_h2.invertY(True)
        self.plot_h2.setXRange(0, 100)
        self.plot_h2.setYRange(100, 0)

        cm = pg.colormap.get('inferno')
        
        self.img_s = pg.ImageItem()
        self.img_s.setLookupTable(cm.getLookupTable())
        self.plot_h1.addItem(self.img_s)
        
        self.img_g = pg.ImageItem()
        self.img_g.setLookupTable(cm.getLookupTable())
        self.plot_h2.addItem(self.img_g)

        l1.addWidget(scr, 1)
        l1.addWidget(self.plot_s, 2)
        l1.addWidget(self.plot_h1, 1) # FSR Strip (narrow column)
        l1.addWidget(self.plot_h2, 2) # FSR Matrix (wider column)

        # PAGE 2: ASYMMETRY CAMERA
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        c_ctrl = QHBoxLayout()
        self.b_c_st = self.c_btn("🟢 START CAM", self.start_cam, "#2E7D32")
        self.b_c_sp = self.c_btn("🔴 STOP CAM", self.stop_cam, "#C62828")
        self.b_c_sp.setEnabled(False)
        self.b_cap = self.c_btn("📸 CAPTURE REPORT", self.capture_report, "#4527A0")
        self.b_cap.setEnabled(False)
        c_ctrl.addWidget(self.b_c_st)
        c_ctrl.addWidget(self.b_c_sp)
        c_ctrl.addStretch()
        c_ctrl.addWidget(self.b_cap)

        self.l_vid = QLabel("CAMERA OFFLINE")
        self.l_vid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.l_vid.setStyleSheet("background-color: #1A1A1A; font-size: 20px; border: 2px dashed #444;")
        self.l_vid.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        l2.addLayout(c_ctrl)
        l2.addWidget(self.l_vid, 1)

        # AI Angle Overlay Metrics Panel
        self.ai_frame = QFrame()
        self.ai_frame.setStyleSheet("background-color: #151515; border: 1px solid #333; border-radius: 8px; padding: 10px;")
        ai_lay = QHBoxLayout(self.ai_frame)
        
        self.lbl_ang1 = QLabel("Açı Bekleniyor...")
        self.lbl_ang2 = QLabel("---")
        self.lbl_ang3 = QLabel("---")
        for lbl in (self.lbl_ang1, self.lbl_ang2, self.lbl_ang3):
            lbl.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: gray;")
            ai_lay.addWidget(lbl)
            
        l2.addWidget(self.ai_frame)

        self.stack.addWidget(p1)
        self.stack.addWidget(p2)
        layout.addWidget(side)
        layout.addWidget(self.stack)

    def c_btn(self, t, f, c):
        b = QPushButton(t)
        b.setStyleSheet(
            f"QPushButton {{ background-color: {c}; color: white; padding: 12px; "
            f"border-radius: 6px; font-weight: bold; border: none;}} "
            f"QPushButton:disabled {{ background-color: #333; color: #777; }}"
        )
        b.clicked.connect(f)
        return b

    def set_mode(self, mode):
        self.current_mode = mode
        if mode == "CORONAL":
            self.b_mod_cor.setStyleSheet("QPushButton { background-color: #555555; color: white; padding: 12px; border-radius: 6px; font-weight: bold; border: none;}")
            self.b_mod_sag.setStyleSheet("QPushButton { background-color: #222222; color: white; padding: 12px; border-radius: 6px; font-weight: bold; border: none;}")
            self.USE_PITCH = False
            self.plot_s.setTitle("CORONAL SCOLIOSIS")
        else:
            self.b_mod_cor.setStyleSheet("QPushButton { background-color: #222222; color: white; padding: 12px; border-radius: 6px; font-weight: bold; border: none;}")
            self.b_mod_sag.setStyleSheet("QPushButton { background-color: #555555; color: white; padding: 12px; border-radius: 6px; font-weight: bold; border: none;}")
            self.USE_PITCH = True
            self.plot_s.setTitle("SAGITTAL KYPHOSIS")

    # === DB ROUTING ===
    def route_db(self):
        self.l_stat.setText("● ROUTING TO CLOUD ARCHIVE...")
        self.l_stat.setStyleSheet("color: #b967ff; font-weight: bold;")
        webbrowser.open("http://localhost:5173")  # Onur'un React Arayüzü

    # === HW & CLOUD LOGIC ===
    def start_hw(self):
        self.b_con.setEnabled(False)
        self.b_dis.setEnabled(True)
        self.telemetry.url = f"ws://{self.ip_input.text().strip()}:81"
        self.telemetry.running = True
        self.telemetry.start()

    def stop_hw(self):
        self.b_con.setEnabled(True)
        self.b_dis.setEnabled(False)
        self.telemetry.stop()
        self.l_imu.setStyleSheet("color:gray;")
        self.l_fsr.setStyleSheet("color:gray;")

    def update_hw_stat(self, s):
        c = "lime" if s == "LIVE" else "red"
        self.l_imu.setText(f"● IMU: {s}")
        self.l_imu.setStyleSheet(f"color: {c};")
        self.l_fsr.setText(f"● FSR: {s}")
        self.l_fsr.setStyleSheet(f"color: {c};")

    def update_telemetry(self, d):
        imus, l_h, r_h = d

        if l_h is not None and r_h is not None:
            # Uçuk değer (Noise/Outlier) Filtresi
            r_med = np.median(r_h)
            r_h = np.clip(r_h, 0.0, r_med + 0.1) # Ani sıçramaları (spike) median + 0.1 (raw) ile sınırla
            
            l_med = np.median(l_h)
            l_h = np.clip(l_h, 0.0, l_med + 0.1)

            # 1. FSR EMA Smoothing Filter
            if self.fsr_l_ema is None:
                self.fsr_l_ema = l_h.copy()
                self.fsr_r_ema = r_h.copy()
            else:
                self.fsr_l_ema = (self.fsr_l_ema * 0.8) + (l_h * 0.2)
                self.fsr_r_ema = (self.fsr_r_ema * 0.8) + (r_h * 0.2)

            # 2. FSR Gain Scaling
            l_h_scaled = self.fsr_l_ema * self.FSR_GAIN
            r_h_scaled = self.fsr_r_ema * self.FSR_GAIN

            try:
                # Upsample and interpolate using OpenCV's cubic filtering (optimized dimensions for 6x lower draw overhead)
                l_h_smooth = cv2.resize(l_h_scaled, (100, 20), interpolation=cv2.INTER_CUBIC)
                r_h_smooth = cv2.resize(r_h_scaled, (100, 100), interpolation=cv2.INTER_CUBIC)
                
                # Clip values to [0.0, 1.0] to prevent mathematical artifacts from bicubic overshoot
                l_h_smooth = np.clip(l_h_smooth, 0.0, 1.0)
                r_h_smooth = np.clip(r_h_smooth, 0.0, 1.0)

                # Rolling max for dynamic range to prevent flickering
                if not hasattr(self, 'fsr_l_max'): self.fsr_l_max = 0.1
                if not hasattr(self, 'fsr_r_max'): self.fsr_r_max = 0.1
                
                self.fsr_l_max = max(0.1, self.fsr_l_max * 0.95 + np.max(l_h_smooth) * 0.05)
                self.fsr_r_max = max(0.1, self.fsr_r_max * 0.95 + np.max(r_h_smooth) * 0.05)

                self.img_s.setImage(l_h_smooth, levels=(0.0, self.fsr_l_max))
                self.img_g.setImage(r_h_smooth, levels=(0.0, self.fsr_r_max))
            except Exception as e:
                print(f"[HEATMAP RESIZE] {e}")
                self.img_s.setImage(l_h_scaled)
                self.img_g.setImage(r_h_scaled)
                
            self.c_fsr_l = l_h_scaled.flatten().tolist()
            self.c_fsr_r = r_h_scaled.flatten().tolist()
            for i, v in enumerate(self.c_fsr_l):
                self.lbl_l[i].setText(f"STRIP {i+1}: {v:.2f}")
            for i, v in enumerate(self.c_fsr_r):
                self.lbl_r[i].setText(f"POINT {i+1}: {v:.2f}")

        if imus:
            self.latest_raw_imus = imus
            
            # IMU Snappy EMA Filter (remove sluggish delay, react instantly)
            if not hasattr(self, 'imu_ema') or self.imu_ema is None:
                self.imu_ema = imus
            else:
                alpha = 0.8  # Snappy factor (80% new, 20% history)
                self.imu_ema = [
                    (self.imu_ema[i][0] * (1 - alpha) + imus[i][0] * alpha,
                     self.imu_ema[i][1] * (1 - alpha) + imus[i][1] * alpha)
                    for i in range(len(imus))
                ]
            imus = self.imu_ema
            
            # 3. IMU Baseline Subtraction (Calibration)
            if self.imu_baseline is not None:
                imus = [(p - bp, r - br) for ((p, r), (bp, br)) in zip(imus, self.imu_baseline)]

            xc, yc = [0.0], [0.0]
            # imus[0] = O_L (sol omuz), imus[1] = O_R (sağ omuz)
            self.c_asym = abs(imus[0][1] - imus[1][1])
            # imus[2..6] = S1..S5 (omurga)
            self.c_spine = [imus[i][1] for i in range(2, 7)]

            VISUAL_GAIN = 1.0  # Amplifies the X-axis displacement (Reduced to 1.0 to reflect realistic movement)
            
            # Sadece Omurga (S1..S4) IMU'larını çiz (Omuzlar spine eğrisine dahil edilmemeli)
            for i in range(2, 7):
                p, r = imus[i]
                angle = p if self.USE_PITCH else r
                xc.append(xc[-1] + SEGMENT_LENGTH * np.sin(np.deg2rad(angle)) * VISUAL_GAIN)
                yc.append(yc[-1] + SEGMENT_LENGTH * np.cos(np.deg2rad(angle)))
                
            for i, (p, r) in enumerate(imus):
                if i in (3, 4): # index 3 and 4 (S2, S3) are filled/interpolated
                    self.lbl_imus[i].setText(f"IMU {i+1}: P:{p:>5.2f} R:{r:>5.2f} (FILL)")
                else:
                    self.lbl_imus[i].setText(f"IMU {i+1}: P:{p:>5.2f} R:{r:>5.2f}")
            try:
                tck, _ = splprep([xc, yc], s=0.05, k=3)
                xn, yn = splev(np.linspace(0, 1, 60), tck)
                self.crv.setData(xn, yn)
                self.pts.setData(xc, yc)
            except Exception as e:
                print(f"[SPLINE] {e}")

    def calibrate_imu(self):
        if self.latest_raw_imus:
            self.imu_baseline = self.latest_raw_imus
            self.l_stat.setText("● IMU CALIBRATED (ZEROED)")
            self.l_stat.setStyleSheet("color: #FF8C00; font-weight: bold;")

    def trigger_cloud(self):
        self.cloud.send_data({
            "patient_id": "ST-2026-001",
            "omuz_asimetrisi": round(self.c_asym, 2),
            "omurga_roll_acileri": [round(x, 2) for x in self.c_spine],
            "serit_basinc_fsr": [round(x, 2) for x in self.c_fsr_l],
            "nokta_basinc_fsr": [round(x, 2) for x in self.c_fsr_r],
            "cam_shoulder_tilt": round(self.c_shoulder_tilt, 2),
            "cam_pelvic_tilt": round(self.c_pelvic_tilt, 2),
            "cam_fhp": round(self.c_fhp, 2),
            "cam_trunk_lean": round(self.c_trunk_lean, 2),
            "cam_face_lean": round(self.c_face_lean, 2)
        })

    # === CAMERA LOGIC ===
    def start_cam(self):
        try:
            cam_idx = int(self.cam_input.text().strip())
        except ValueError:
            cam_idx = 0
        cap = cv2.VideoCapture(cam_idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                self.cap = cap
            else:
                cap.release()
                self.l_stat.setText(f"● KAMERA OKUMA HATASI")
                return
        else:
            self.l_stat.setText(f"● KAMERA ACILAMADI")
            return
        self.b_c_st.setEnabled(False)
        self.b_c_sp.setEnabled(True)
        self.b_cap.setEnabled(True)
        self.cam_timer.start(30)

    def stop_cam(self):
        self.cam_timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.b_c_st.setEnabled(True)
        self.b_c_sp.setEnabled(False)
        self.b_cap.setEnabled(False)
        self.l_vid.setText("CAMERA OFFLINE")

    def update_cam(self):
        if self.cap is None: return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame_cv = frame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            
            # Sadece AI boştayken yeni kareyi gönder (Queue/Bellek patlamasını önler)
            if not self.is_processing:
                self.is_processing = True
                self.mp_timestamp += 33  # ~30 FPS sabit artış
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                # detect_async arka planda çalışır
                self.pose_tracker.detect_async(mp_image, self.mp_timestamp)
            
            # Çizim için arka plandan gelen en son sonucu (callback) kullan
            if self.latest_result and self.latest_result.pose_landmarks and len(self.latest_result.pose_landmarks) > 0:
                lm_list = self.latest_result.pose_landmarks[0]
                self.latest_landmarks = lm_list
                
                # Sadece istenen noktalar (Burun, Kulak, Torso, Ön Kol, Tüm Bacak)
                desired_nodes = [0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
                
                # Güçlü EMA Filtresi
                alpha = 0.15
                smoothed_points = {}
                
                for idx in desired_nodes:
                    lm = lm_list[idx]
                    if lm.visibility > 0.5:
                        raw_x = lm.x * w
                        raw_y = lm.y * h
                        
                        # Omuzların (11, 12) anatomik olarak biraz aşağıda görünme sorununu 
                        # çözmek için noktaları yapay olarak %2 oranında yukarı kaydırıyoruz.
                        if idx in [11, 12]:
                            raw_y -= h * 0.02
                        
                        if idx not in self.lm_ema:
                            self.lm_ema[idx] = (raw_x, raw_y)
                        else:
                            px, py = self.lm_ema[idx]
                            self.lm_ema[idx] = (px * (1 - alpha) + raw_x * alpha, py * (1 - alpha) + raw_y * alpha)
                            
                        cx, cy = int(self.lm_ema[idx][0]), int(self.lm_ema[idx][1])
                        smoothed_points[idx] = (cx, cy)
                
                # Google Official Demo Stili Renkleri
                color_point_inner = (255, 255, 255) # Beyaz
                color_point_outer = (0, 0, 255)     # Kırmızı
                color_line = (255, 255, 255)        # Beyaz
                
                if self.current_mode == "CORONAL":
                    # İskelet bağlantılarını çiz (Önce çizgiler)
                    connections = [
                        (11, 12), (23, 24), (11, 23), (12, 24), # Torso
                        (11, 13), (13, 15), # Sol Kol
                        (12, 14), (14, 16), # Sağ Kol
                        (23, 25), (24, 26), # Üst Bacak
                        (25, 27), (26, 28)  # Alt Bacak
                    ]
                    for p1, p2 in connections:
                        if p1 in smoothed_points and p2 in smoothed_points:
                            cv2.line(frame_rgb, smoothed_points[p1], smoothed_points[p2], color_line, 2)
                            
                    if 11 in smoothed_points and 12 in smoothed_points:
                        lx, ly = smoothed_points[11]
                        rx, ry = smoothed_points[12]
                        dx_sh = rx - lx
                        dy_sh = ry - ly
                        shoulder_tilt = math.degrees(math.atan2(dy_sh, dx_sh))
                        self.c_shoulder_tilt = shoulder_tilt
                        cv2.line(frame_rgb, (lx, ly), (rx, ry), (255, 0, 0), 4)
                        self.lbl_ang1.setText(f"SHOULDER TILT: {shoulder_tilt:.1f}°")
                        self.lbl_ang1.setStyleSheet("color: #ff6464;")
                        
                    if 23 in smoothed_points and 24 in smoothed_points:
                        lx, ly = smoothed_points[23]
                        rx, ry = smoothed_points[24]
                        dx_hp = rx - lx
                        dy_hp = ry - ly
                        pelvic_tilt = math.degrees(math.atan2(dy_hp, dx_hp))
                        self.c_pelvic_tilt = pelvic_tilt
                        cv2.line(frame_rgb, (lx, ly), (rx, ry), (0, 0, 255), 4)
                        self.lbl_ang2.setText(f"PELVIC TILT: {pelvic_tilt:.1f}°")
                        self.lbl_ang2.setStyleSheet("color: #6464ff;")

                    self.lbl_ang3.setText("---")
                    self.lbl_ang3.setStyleSheet("color: gray;")

                elif self.current_mode == "SAGITTAL":
                    # Hangi tarafın kameraya dönük olduğunu bul (Sağ veya Sol)
                    nose_idx = 0 if 0 in smoothed_points else None
                    ear_idx = 8 if 8 in smoothed_points else 7 if 7 in smoothed_points else None
                    sh_idx = 12 if 12 in smoothed_points else 11 if 11 in smoothed_points else None
                    hip_idx = 24 if 24 in smoothed_points else 23 if 23 in smoothed_points else None
                    
                    if ear_idx and sh_idx and hip_idx:
                        ex, ey = smoothed_points[ear_idx]
                        sx, sy = smoothed_points[sh_idx]
                        hx, hy = smoothed_points[hip_idx]
                        
                        # FHP (İleri Baş Postürü) Açısı
                        dx_fhp = abs(ex - sx)
                        dy_fhp = abs(sy - ey)
                        fhp_angle = math.degrees(math.atan2(dx_fhp, dy_fhp)) if dy_fhp != 0 else 0
                        
                        # Trunk Lean (Gövde Eğimi / Kifoz İndeksi)
                        dx_trunk = abs(sx - hx)
                        dy_trunk = abs(hy - sy)
                        trunk_lean = math.degrees(math.atan2(dx_trunk, dy_trunk)) if dy_trunk != 0 else 0
                        
                        # Çizimler (Sagittal Üçgen)
                        cv2.line(frame_rgb, (ex, ey), (sx, sy), (255, 255, 0), 4) # Kulak - Omuz (Sarı)
                        cv2.line(frame_rgb, (sx, sy), (hx, hy), (0, 255, 255), 4) # Omuz - Kalça (Camgöbeği)
                        
                        # Dikey Referans Çizgileri (Kalçadan yukarı ve Omuzdan yukarı)
                        cv2.line(frame_rgb, (hx, hy), (hx, hy - 300), (100, 100, 100), 2, cv2.LINE_AA)
                        cv2.line(frame_rgb, (sx, sy), (sx, sy - 200), (100, 100, 100), 2, cv2.LINE_AA)
                        
                        self.c_fhp = fhp_angle
                        self.c_trunk_lean = trunk_lean

                        # Arayüze Yazdır
                        self.lbl_ang1.setText(f"FHP (HEAD): {fhp_angle:.1f}°")
                        self.lbl_ang1.setStyleSheet("color: #ffff00;")
                        
                        self.lbl_ang2.setText(f"TRUNK (KYPHOSIS): {trunk_lean:.1f}°")
                        self.lbl_ang2.setStyleSheet("color: #00ffff;")

                        # Yüz (Burun) - Kalça Eğimi (Kapsamlı İleri Eğilim)
                        if nose_idx is not None:
                            nx, ny = smoothed_points[nose_idx]
                            dx_face = abs(nx - hx)
                            dy_face = abs(hy - ny)
                            face_lean = math.degrees(math.atan2(dx_face, dy_face)) if dy_face != 0 else 0
                            self.c_face_lean = face_lean
                            
                            # Burundan kalçaya mor çizgi
                            cv2.line(frame_rgb, (nx, ny), (hx, hy), (255, 0, 255), 2, cv2.LINE_AA)
                            self.lbl_ang3.setText(f"TOTAL LEAN (NOSE): {face_lean:.1f}°")
                            self.lbl_ang3.setStyleSheet("color: #ff00ff;")
                        else:
                            self.lbl_ang3.setText("NOSE NOT DETECTED")
                            self.lbl_ang3.setStyleSheet("color: gray;")
                    else:
                        self.lbl_ang1.setText("---")
                        self.lbl_ang1.setStyleSheet("color: gray;")
                        self.lbl_ang2.setText("---")
                        self.lbl_ang2.setStyleSheet("color: gray;")
                        self.lbl_ang3.setText("---")
                        self.lbl_ang3.setStyleSheet("color: gray;")
                        
                # Noktaları Çiz (Tüm modlarda noktalar en üstte görünsün diye sonda çiziyoruz)
                for idx in desired_nodes:
                    if idx in smoothed_points:
                        cx, cy = smoothed_points[idx]
                        cv2.circle(frame_rgb, (cx, cy), 5, color_point_outer, -1) # Kırmızı dış çizgi
                        cv2.circle(frame_rgb, (cx, cy), 3, color_point_inner, -1) # Beyaz iç dolgu
            
            q_img = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.l_vid.setPixmap(QPixmap.fromImage(q_img).scaled(self.l_vid.width(), self.l_vid.height(), Qt.AspectRatioMode.KeepAspectRatio))

    def capture_report(self):
        if self.cap and self.cap.isOpened() and self.current_frame_cv is not None:
            self.cam_timer.stop()
            annotated_frame = self.current_frame_cv.copy()
            if self.latest_landmarks:
                h, w = annotated_frame.shape[:2]
                lm_list = self.latest_landmarks
                if self.current_mode == "CORONAL":
                    l_sh, r_sh = lm_list[11], lm_list[12]
                    cv2.line(annotated_frame, (int(l_sh.x * w), int(l_sh.y * h)), (int(r_sh.x * w), int(r_sh.y * h)), (255, 0, 0), 3)
                elif self.current_mode == "SAGITTAL":
                    ear, sh = lm_list[8], lm_list[12]
                    cv2.line(annotated_frame, (int(ear.x * w), int(ear.y * h)), (int(sh.x * w), int(sh.y * h)), (255, 255, 0), 3)
                    nose, hip = lm_list[0], lm_list[24]
                    cv2.line(annotated_frame, (int(nose.x * w), int(nose.y * h)), (int(hip.x * w), int(hip.y * h)), (255, 0, 255), 3)
            
            cv2.imwrite("patient_report.jpg", annotated_frame)
            self.l_stat.setText("● REPORT CAPTURED: patient_report.jpg SAVED.")
            self.l_stat.setStyleSheet("color: lime; font-weight: bold;")

    def closeEvent(self, event):
        self.cloud_timer.stop()
        self.telemetry.stop()
        self.cloud.stop()
        self.stop_cam()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ScoliosisMonitor()
    window.show()
    sys.exit(app.exec())
