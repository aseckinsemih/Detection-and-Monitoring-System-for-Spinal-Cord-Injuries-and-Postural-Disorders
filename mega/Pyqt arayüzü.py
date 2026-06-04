import sys
import json
import numpy as np
from scipy.interpolate import splprep, splev

# PyQt6 & PyQtGraph Kütüphaneleri
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import websocket

# =================================================================================
# --- SISTEM KONFIGURASYONU ---
# =================================================================================
ESP32_IP = "10.158.24.15"   # <--- Serial Monitör'de gördüğün GÜNCEL IP'yi buraya yaz!

IMU_COUNT = 7          
LEFT_STRIP_COUNT = 5   
RIGHT_POINT_COUNT = 9  
SEGMENT_LENGTH = 0.6   

# =================================================================================
# PART 1: TELEMETRİ İŞÇİSİ (DONANIM HABERLEŞMESİ)
# =================================================================================
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
                    msg = ws.recv()
                    if msg: self.parse_data(msg)
            except Exception:
                self.status_signal.emit("OFFLINE")
                QThread.sleep(1) # Tekrar denemeden önce 1 saniye bekle

    def parse_data(self, raw_data):
        try:
            raw_data = raw_data.strip()
            # 1. Basınç (FSR) JSON Verisi Gelirse
            if raw_data.startswith('{'):
                p = json.loads(raw_data)
                l = [float(list(d.values())[0]) for d in p['fsr_sensors']]
                r = [float(list(d.values())[0]) for d in p['nokta_sensors']]
                l_arr = np.array(l).reshape(1, 5)
                r_arr = np.array(r).reshape(3, 3)
                self.data_signal.emit((None, l_arr, r_arr))
            
            # 2. IMU Verisi Gelirse
            elif raw_data.startswith('$') or "*" in raw_data:
                clean_data = raw_data.replace('$', '')
                parts = [float(x) for x in clean_data.split('*') if x]
                if len(parts) >= 14:
                    imus = [(parts[i], parts[i+1]) for i in range(0, 14, 2)]
                    self.data_signal.emit((imus, None, None))
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.wait()

# =================================================================================
# PART 2: V27 CORE CONSOLE (SADECE DONANIM VE EKRAN)
# =================================================================================
class ScoliosisCoreMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("V27 Core Platform | Hardware Telemetry")
        self.resize(1600, 950)
        self.setStyleSheet("background-color: #121212; color: white; font-family: Arial;")

        self.init_ui()

        # Telemetry Worker Bağlantısı
        self.telemetry = TelemetryWorker()
        self.telemetry.data_signal.connect(self.process_live_data)
        self.telemetry.status_signal.connect(self.update_hardware_status)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0,0,0,0)

        # === SIDEBAR ===
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet("background-color: #1E1E1E;")
        sidebar_layout = QVBoxLayout(sidebar)

        title = QLabel("HARDWARE CORE")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title)
        sidebar_layout.addSpacing(30)

        self.btn_connect = self.create_btn("▶ CONNECT HARDWARE", self.start_stream, "#2E7D32")
        self.btn_disconnect = self.create_btn("■ DISCONNECT", self.stop_stream, "#C62828")
        self.btn_disconnect.setEnabled(False)
        sidebar_layout.addWidget(self.btn_connect)
        sidebar_layout.addWidget(self.btn_disconnect)

        # Durum Göstergeleri
        diag_frame = QFrame()
        diag_frame.setStyleSheet("background-color: #121212; border-radius: 5px;")
        diag_layout = QVBoxLayout(diag_frame)
        self.lbl_imu_stat = QLabel("● IMU ARRAY: WAIT")
        self.lbl_fsr_stat = QLabel("● PRESSURE: WAIT")
        self.lbl_imu_stat.setStyleSheet("color: gray;")
        self.lbl_fsr_stat.setStyleSheet("color: gray;")
        diag_layout.addWidget(self.lbl_imu_stat)
        diag_layout.addWidget(self.lbl_fsr_stat)
        sidebar_layout.addWidget(diag_frame)

        sidebar_layout.addStretch()

        # === ANA EKRAN (DATA & GRAFİKLER) ===
        home_widget = QWidget()
        home_layout = QHBoxLayout(home_widget)
        
        # 1. Sol Panel (Yazılı Veriler)
        data_scroll = QScrollArea()
        data_scroll.setFixedWidth(250)
        data_scroll.setWidgetResizable(True)
        data_scroll.setStyleSheet("background-color: #1A1A1A; border: none;")
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        self.imu_labels = [QLabel(f"IMU {i+1}: --") for i in range(IMU_COUNT)]
        for lbl in self.imu_labels: 
            lbl.setFont(QFont("Consolas", 10))
            self.scroll_layout.addWidget(lbl)
            
        self.scroll_layout.addSpacing(15)
        title_pres = QLabel("--- PRESSURE MAP ---")
        title_pres.setStyleSheet("color: #55FFFF; font-weight: bold;")
        self.scroll_layout.addWidget(title_pres)
        
        self.left_labels = [QLabel(f"STRIP {i+1}: --") for i in range(LEFT_STRIP_COUNT)]
        self.right_labels = [QLabel(f"POINT {i+1}: --") for i in range(RIGHT_POINT_COUNT)]
        for lbl in self.left_labels + self.right_labels: self.scroll_layout.addWidget(lbl)
        self.scroll_layout.addStretch()
        data_scroll.setWidget(scroll_content)
        
        # 2. Orta Panel (Omurga Eğrisi)
        pg.setConfigOptions(antialias=True)
        self.spine_plot = pg.PlotWidget(title="CORONAL PLANE (SCOLIOSIS)")
        self.spine_plot.setBackground('#1A1A1A')
        self.spine_plot.showGrid(x=True, y=True, alpha=0.2)
        self.spine_plot.setXRange(-2, 2)
        self.spine_plot.setYRange(0, 5)
        self.line_curve = self.spine_plot.plot(pen=pg.mkPen('#55FF55', width=5))
        self.scatter_pts = self.spine_plot.plot(pen=None, symbol='o', symbolBrush='w', symbolSize=12)

        # 3. Sağ Panel (Isı Haritaları)
        self.heat_plot = pg.PlotWidget(title="PRESSURE MATRIX")
        self.heat_plot.setBackground('#1A1A1A')
        self.heat_plot.invertY(True) 
        
        colormap = pg.colormap.get('inferno')
        
        self.img_strip = pg.ImageItem()
        self.img_strip.setLookupTable(colormap.getLookupTable())
        self.heat_plot.addItem(self.img_strip)
        
        self.img_grid = pg.ImageItem()
        self.img_grid.setLookupTable(colormap.getLookupTable())
        self.heat_plot.addItem(self.img_grid)
        self.img_grid.setPos(2, 0) # 3x3 matrisi sağa kaydır

        home_layout.addWidget(data_scroll, 1)
        home_layout.addWidget(self.spine_plot, 2)
        home_layout.addWidget(self.heat_plot, 2)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(home_widget, 1)

    def create_btn(self, text, func, color):
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {color}; color: white; padding: 12px; 
                          border-radius: 6px; font-weight: bold; font-size: 13px; border: none;}}
            QPushButton:hover {{ background-color: #555555; }}
            QPushButton:disabled {{ background-color: #333333; color: #777777; }}
        """)
        btn.clicked.connect(func)
        return btn

    def start_stream(self):
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.telemetry.start()

    def stop_stream(self):
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.telemetry.stop()
        self.lbl_imu_stat.setText("● IMU ARRAY: OFFLINE"); self.lbl_imu_stat.setStyleSheet("color: gray;")
        self.lbl_fsr_stat.setText("● PRESSURE: OFFLINE"); self.lbl_fsr_stat.setStyleSheet("color: gray;")

    def update_hardware_status(self, stat):
        if stat == "LIVE":
            self.lbl_imu_stat.setText("● IMU ARRAY: LIVE"); self.lbl_imu_stat.setStyleSheet("color: lime;")
            self.lbl_fsr_stat.setText("● PRESSURE: LIVE"); self.lbl_fsr_stat.setStyleSheet("color: lime;")
        elif stat == "CONNECTING...":
            self.lbl_imu_stat.setText("● CONNECTING..."); self.lbl_imu_stat.setStyleSheet("color: yellow;")
        else:
            self.lbl_imu_stat.setText("● OFFLINE"); self.lbl_imu_stat.setStyleSheet("color: red;")
            self.lbl_fsr_stat.setText("● OFFLINE"); self.lbl_fsr_stat.setStyleSheet("color: red;")

    def process_live_data(self, data_tuple):
        imus, l_h, r_h = data_tuple
        
        # --- ISI HARİTASI GÜNCELLEMESİ (.T İLE EKSEN DÜZELTİLDİ) ---
        if l_h is not None and r_h is not None:
            self.img_strip.setImage(l_h.T) 
            self.img_grid.setImage(r_h.T)
            
            for i, val in enumerate(l_h.flatten()): self.left_labels[i].setText(f"STRIP {i+1}: {val:.2f}")
            for i, val in enumerate(r_h.flatten()): self.right_labels[i].setText(f"POINT {i+1}: {val:.2f}")

        # --- IMU & OMURGA ÇİZGİSİ GÜNCELLEMESİ ---
        if imus:
            xc, yc = [0.0], [0.0]
            for i, (p, r) in enumerate(imus):
                xc.append(xc[-1] + SEGMENT_LENGTH * np.sin(np.deg2rad(r)))
                yc.append(yc[-1] + SEGMENT_LENGTH * np.cos(np.deg2rad(r)))
                self.imu_labels[i].setText(f"IMU {i+1}: P:{p:>5.2f} R:{r:>5.2f}")

            try:
                tck, _ = splprep([xc, yc], s=0.05, k=3)
                xn, yn = splev(np.linspace(0, 1, 60), tck)
                self.line_curve.setData(xn, yn)
                self.scatter_pts.setData(xc, yc)
            except Exception:
                pass

    def closeEvent(self, event):
        self.telemetry.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ScoliosisCoreMonitor()
    window.show()
    sys.exit(app.exec())