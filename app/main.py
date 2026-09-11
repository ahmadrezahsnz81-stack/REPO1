import base64
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSlider, QSpinBox, QDoubleSpinBox, QVBoxLayout, QWidget
)

APP_TITLE = "DJAR RVC Studio"
DEFAULT_API = "http://127.0.0.1:7897"
CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "DJAR RVC Studio"
CONFIG_FILE = CONFIG_DIR / "settings.json"

STYLESHEET = """
QMainWindow, QWidget { background:#0b0e13; color:#e9edf5; font-family:'Segoe UI'; font-size:10pt; }
QScrollArea { border:0; background:#0b0e13; }
QFrame#topbar { background:#0f131a; border-bottom:1px solid #242b36; }
QFrame#card { background:#121720; border:1px solid #242c38; border-radius:14px; }
QFrame#drop { background:#0e131b; border:1px dashed #394657; border-radius:12px; }
QLabel#title { color:#ffffff; font-size:25pt; font-weight:700; }
QLabel#subtitle { color:#8792a5; font-size:9.5pt; }
QLabel#section { color:#f4f7fb; font-size:11pt; font-weight:700; }
QLabel#muted { color:#7f8a9d; }
QLabel#value { color:#dbe2ed; font-weight:600; }
QLabel#statusOnline { color:#5ee28a; font-weight:700; }
QLabel#statusOffline { color:#ff7181; font-weight:700; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#0c1016; color:#e8edf5; border:1px solid #2b3441; border-radius:8px; padding:9px 10px; min-height:18px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border:1px solid #6f7cff; }
QComboBox QAbstractItemView { background:#111720; color:#e8edf5; selection-background-color:#343d75; }
QPushButton { background:#1a212c; color:#e9edf5; border:1px solid #303a48; border-radius:8px; padding:9px 14px; font-weight:600; }
QPushButton:hover { background:#222b38; border-color:#46546a; }
QPushButton:pressed { background:#151b23; }
QPushButton#primary { background:#6975ff; border:1px solid #7e88ff; color:white; padding:13px; font-size:11pt; font-weight:700; }
QPushButton#primary:hover { background:#7a85ff; }
QPushButton#ghost { background:transparent; border:0; color:#9ca8ba; padding:6px; }
QProgressBar { background:#0b1016; border:0; border-radius:5px; height:9px; text-align:center; color:transparent; }
QProgressBar::chunk { background:#6975ff; border-radius:5px; }
QSlider::groove:horizontal { height:4px; background:#2a3340; border-radius:2px; }
QSlider::handle:horizontal { width:16px; height:16px; margin:-6px 0; background:#e9edf5; border-radius:8px; }
QSlider::sub-page:horizontal { background:#6975ff; border-radius:2px; }
QFrame#pill { background:#151c26; border:1px solid #293341; border-radius:9px; }
"""


def load_settings():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.finished.emit(self.fn(self.progress))
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 780)
        self.setMinimumSize(980, 680)
        self.settings = load_settings()
        self.last_output = ""
        self.setStyleSheet(STYLESHEET)
        self.build_ui()
        self.restore_settings()

    def build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        top = QFrame(objectName="topbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(28, 20, 28, 18)
        brand = QVBoxLayout()
        title = QLabel("DJAR RVC Studio", objectName="title")
        subtitle = QLabel("Professional local voice conversion workstation", objectName="subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        top_layout.addLayout(brand)
        top_layout.addStretch()
        self.connection_badge = QLabel("●  DISCONNECTED", objectName="statusOffline")
        self.connection_badge.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.connection_badge)
        root_layout.addWidget(top)

        api_bar = QFrame()
        api_layout = QHBoxLayout(api_bar)
        api_layout.setContentsMargins(28, 12, 28, 12)
        api_layout.addWidget(QLabel("RVC API"))
        self.api_edit = QLineEdit(DEFAULT_API)
        self.api_edit.setPlaceholderText(DEFAULT_API)
        api_layout.addWidget(self.api_edit, 1)
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        api_layout.addWidget(self.test_btn)
        root_layout.addWidget(api_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 12, 28, 28)
        content_layout.setSpacing(16)
        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        content_layout.addLayout(grid)

        left = self.card("VOICE & AUDIO")
        ll = left.layout()
        ll.addWidget(self.section_label("Voice model"))
        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("Voice / Speaker ID 0", "0")
        voice_row.addWidget(self.voice_combo, 1)
        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.clicked.connect(self.refresh_voices)
        voice_row.addWidget(self.refresh_btn)
        ll.addLayout(voice_row)
        ll.addSpacing(8)
        ll.addWidget(self.section_label("Input audio"))
        drop = QFrame(objectName="drop")
        dl = QVBoxLayout(drop)
        dl.setContentsMargins(18, 20, 18, 20)
        self.audio_label = QLabel("🎵  No audio selected")
        self.audio_label.setAlignment(Qt.AlignCenter)
        self.audio_label.setObjectName("muted")
        dl.addWidget(self.audio_label)
        browse = QPushButton("Browse audio file")
        browse.clicked.connect(self.pick_audio)
        dl.addWidget(browse)
        ll.addWidget(drop)
        self.audio_path = QLineEdit()
        self.audio_path.setVisible(False)
        ll.addWidget(self.audio_path)
        ll.addSpacing(8)
        ll.addWidget(self.section_label("F0 algorithm"))
        self.f0_combo = QComboBox()
        self.f0_combo.addItems(["RMVPE", "CREPE", "Harvest", "PM"])
        self.f0_combo.setCurrentIndex(0)
        ll.addWidget(self.f0_combo)
        grid.addWidget(left, 0, 0)

        right = self.card("VOICE CONTROL")
        rl = right.layout()
        self.pitch_slider, self.pitch_value = self.add_slider(rl, "Pitch / Transpose", -12, 12, 0, " semitones")
        self.index_slider, self.index_value = self.add_slider(rl, "Index / Feature ratio", 0, 100, 75, "%")
        self.protect_slider, self.protect_value = self.add_slider(rl, "Protect breath / consonants", 0, 50, 33, "%")
        rl.addSpacing(4)
        adv_title = QHBoxLayout()
        adv_title.addWidget(self.section_label("Advanced settings"))
        adv_title.addStretch()
        rl.addLayout(adv_title)
        self.filter_slider, self.filter_value = self.add_slider(rl, "Median filter radius", 0, 7, 3, "")
        self.resample_slider, self.resample_value = self.add_slider(rl, "Resample rate", 0, 48000, 0, " Hz")
        self.rms_slider, self.rms_value = self.add_slider(rl, "Volume envelope mix", 0, 100, 25, "%")
        rl.addWidget(self.section_label("Feature index"))
        idxrow = QHBoxLayout()
        self.index_path = QLineEdit()
        self.index_path.setPlaceholderText("Optional .index file")
        idxrow.addWidget(self.index_path, 1)
        idxbtn = QPushButton("Browse")
        idxbtn.clicked.connect(self.pick_index)
        idxrow.addWidget(idxbtn)
        rl.addLayout(idxrow)
        grid.addWidget(right, 0, 1)

        output = self.card("CONVERSION")
        ol = output.layout()
        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("muted")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.percent_label = QLabel("0%", objectName="value")
        status_row.addWidget(self.percent_label)
        ol.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        ol.addWidget(self.progress)
        btnrow = QHBoxLayout()
        self.convert_btn = QPushButton("✦  CONVERT AUDIO", objectName="primary")
        self.convert_btn.clicked.connect(self.convert)
        btnrow.addWidget(self.convert_btn, 2)
        self.output_btn = QPushButton("Open Output")
        self.output_btn.clicked.connect(self.open_output)
        btnrow.addWidget(self.output_btn, 1)
        ol.addLayout(btnrow)
        content_layout.addWidget(output)

        tip = QLabel("RVC stays on your PC. DJAR RVC Studio communicates with the local API and saves converted audio beside your source file.", objectName="muted")
        tip.setWordWrap(True)
        content_layout.addWidget(tip)

    def card(self, title):
        frame = QFrame(objectName="card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(9)
        layout.addWidget(self.section_label(title))
        return frame

    def section_label(self, text):
        return QLabel(text, objectName="section")

    def add_slider(self, layout, label, lo, hi, value, suffix):
        row = QVBoxLayout()
        head = QHBoxLayout()
        lab = QLabel(label)
        val = QLabel(objectName="value")
        val.setText(f"{value}{suffix}")
        head.addWidget(lab)
        head.addStretch()
        head.addWidget(val)
        row.addLayout(head)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        slider.valueChanged.connect(lambda x, v=val, s=suffix: v.setText(f"{x}{s}"))
        row.addWidget(slider)
        layout.addLayout(row)
        return slider, val

    def restore_settings(self):
        self.api_edit.setText(self.settings.get("api", DEFAULT_API))
        self.f0_combo.setCurrentIndex(self.settings.get("f0", 0))
        self.index_slider.setValue(self.settings.get("index_rate", 75))
        self.protect_slider.setValue(self.settings.get("protect", 33))
        self.filter_slider.setValue(self.settings.get("filter", 3))
        self.resample_slider.setValue(self.settings.get("resample", 0))
        self.rms_slider.setValue(self.settings.get("rms", 25))
        self.pitch_slider.setValue(self.settings.get("pitch", 0))

    def save_current_settings(self):
        save_settings({
            "api": self.api_edit.text().strip(), "f0": self.f0_combo.currentIndex(),
            "index_rate": self.index_slider.value(), "protect": self.protect_slider.value(),
            "filter": self.filter_slider.value(), "resample": self.resample_slider.value(),
            "rms": self.rms_slider.value(), "pitch": self.pitch_slider.value()
        })

    def api_url(self, path):
        return self.api_edit.text().strip().rstrip("/") + path

    def set_busy(self, busy):
        self.convert_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.test_btn.setEnabled(not busy)

    def run_worker(self, fn, finished):
        thread = QThread(self)
        worker = Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(finished)
        worker.failed.connect(self.worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._thread = thread

    def test_connection(self):
        self.status_label.setText("Testing RVC API…")
        self.test_btn.setEnabled(False)
        def work(progress):
            r = requests.post(self.api_url("/run/infer_clean"), json={"data": []}, timeout=15)
            r.raise_for_status()
            return True
        def done(_):
            self.test_btn.setEnabled(True)
            self.connection_badge.setText("●  RVC CONNECTED")
            self.connection_badge.setObjectName("statusOnline")
            self.connection_badge.style().unpolish(self.connection_badge); self.connection_badge.style().polish(self.connection_badge)
            self.status_label.setText("Connected to RVC API")
        self.run_worker(work, done)

    def refresh_voices(self):
        self.status_label.setText("Refreshing voice models…")
        def work(progress):
            r = requests.post(self.api_url("/run/infer_refresh"), json={"data": []}, timeout=30)
            r.raise_for_status()
            return r.json().get("data", [])
        def done(data):
            self.voice_combo.clear()
            values = []
            if isinstance(data, list):
                for item in data:
                    text = str(item)
                    if text.strip(): values.append(text)
            if not values:
                values = ["Voice / Speaker ID 0"]
            for i, text in enumerate(values):
                self.voice_combo.addItem(text, str(i))
            self.status_label.setText(f"Voice list refreshed · {len(values)} option(s)")
        self.run_worker(work, done)

    def pick_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select audio", "", "Audio files (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*.*)")
        if path:
            self.audio_path.setText(path)
            self.audio_label.setText("🎵  " + Path(path).name)
            self.audio_label.setObjectName("value")
            self.audio_label.style().unpolish(self.audio_label); self.audio_label.style().polish(self.audio_label)

    def pick_index(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select feature index", "", "Index files (*.index);;All files (*.*)")
        if path: self.index_path.setText(path)

    def convert(self):
        audio = self.audio_path.text().strip()
        if not audio or not os.path.isfile(audio):
            QMessageBox.warning(self, "Input required", "Please select a valid audio file first.")
            return
        self.save_current_settings()
        self.set_busy(True)
        self.progress.setValue(5)
        self.percent_label.setText("5%")
        self.status_label.setText("Preparing conversion…")
        def work(progress):
            progress.emit(15, "Sending audio to RVC…")
            empty_f0 = {"name":"none.txt", "data":"data:text/plain;base64," + base64.b64encode(b"").decode()}
            voice_id = self.voice_combo.currentData()
            if voice_id is None: voice_id = "0"
            payload = {"data":[
                int(float(voice_id)), audio, self.pitch_slider.value(), empty_f0,
                self.f0_combo.currentText().lower(), self.index_path.text().strip(),
                "", self.index_slider.value()/100.0, self.filter_slider.value(),
                self.resample_slider.value(), self.rms_slider.value()/100.0,
                self.protect_slider.value()/100.0
            ]}
            progress.emit(25, "RVC is processing…")
            r = requests.post(self.api_url("/run/infer_convert"), json=payload, timeout=3600)
            r.raise_for_status()
            obj = r.json()
            data = obj.get("data", [])
            audio_obj = data[1] if len(data) > 1 else None
            if not isinstance(audio_obj, dict) or "data" not in audio_obj:
                raise RuntimeError("RVC returned no converted audio data.")
            raw = audio_obj["data"].split(",", 1)[-1]
            out_dir = Path(audio).parent / "DJAR_RVC_Output"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / (Path(audio).stem + "_RVC.wav")
            out.write_bytes(base64.b64decode(raw))
            progress.emit(100, "Conversion complete")
            return str(out)
        def done(out):
            self.set_busy(False)
            self.last_output = out
            self.progress.setValue(100)
            self.percent_label.setText("100%")
            self.status_label.setText("✓ Conversion complete")
            box = QMessageBox(self)
            box.setWindowTitle("Conversion complete")
            box.setText("Your converted audio is ready.")
            box.setInformativeText(out)
            box.setStandardButtons(QMessageBox.Ok)
            box.exec()
        self._worker_progress = lambda p, msg: self.update_progress(p, msg)
        def progress_done(_): pass
        # Recreate worker explicitly to expose progress signals.
        thread = QThread(self)
        worker = Worker(work)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.update_progress)
        worker.finished.connect(done)
        worker.failed.connect(self.worker_failed)
        worker.finished.connect(thread.quit); worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start(); self._thread = thread

    def update_progress(self, value, message):
        self.progress.setValue(max(0, min(100, int(value))))
        self.percent_label.setText(f"{int(value)}%")
        self.status_label.setText(message)

    def worker_failed(self, msg):
        self.set_busy(False)
        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("✕ Operation failed")
        QMessageBox.critical(self, "RVC Error", msg)

    def open_output(self):
        path = self.last_output
        if not path:
            audio = self.audio_path.text().strip()
            if audio: path = str(Path(audio).parent / "DJAR_RVC_Output")
        if path:
            target = Path(path)
            if target.is_file(): target = target.parent
            target.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def closeEvent(self, event):
        self.save_current_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
