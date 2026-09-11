import base64
import json
import os
import sys
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QComboBox, QScrollArea, QSlider, QVBoxLayout, QWidget

APP_TITLE = "DJAR RVC Studio"
DEFAULT_API = "http://127.0.0.1:7897"
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "DJAR RVC Studio"
CONFIG_FILE = CONFIG_DIR / "settings.json"

STYLE = """
QMainWindow,QWidget{background:#0a0d12;color:#e8edf5;font-family:'Segoe UI';font-size:10pt}
QFrame#top{background:#0e1219;border-bottom:1px solid #242b36}
QFrame#card{background:#121821;border:1px solid #252e3a;border-radius:14px}
QFrame#drop{background:#0d131b;border:1px dashed #3b485a;border-radius:12px}
QLabel#title{font-size:26pt;font-weight:700;color:#fff}
QLabel#subtitle,QLabel#muted{color:#8490a3}
QLabel#section{font-size:11pt;font-weight:700;color:#f4f7fb}
QLabel#value{font-weight:700;color:#dce4ef}
QLabel#online{font-weight:700;color:#5ee58a}
QLabel#offline{font-weight:700;color:#ff7180}
QLineEdit,QComboBox{background:#0b1016;color:#e8edf5;border:1px solid #2b3543;border-radius:8px;padding:9px 10px}
QLineEdit:focus,QComboBox:focus{border:1px solid #707bff}
QComboBox QAbstractItemView{background:#111720;color:#fff;selection-background-color:#353f78}
QPushButton{background:#19212c;color:#e8edf5;border:1px solid #303b49;border-radius:8px;padding:9px 14px;font-weight:600}
QPushButton:hover{background:#232d3a;border-color:#48576c}
QPushButton#primary{background:#6975ff;color:white;border:1px solid #7e88ff;padding:13px;font-size:11pt;font-weight:700}
QPushButton#primary:hover{background:#7a85ff}
QProgressBar{background:#0a0f15;border:0;border-radius:5px;height:9px;text-align:center;color:transparent}
QProgressBar::chunk{background:#6975ff;border-radius:5px}
QSlider::groove:horizontal{height:4px;background:#293340;border-radius:2px}
QSlider::sub-page:horizontal{background:#6975ff;border-radius:2px}
QSlider::handle:horizontal{width:16px;height:16px;margin:-6px 0;background:#edf1f7;border-radius:8px}
"""


def load_settings():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
        except Exception as exc:
            self.failed.emit(str(exc))


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 800)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(STYLE)
        self.last_output = ""
        self.saved = load_settings()
        self.thread = None
        self.build()
        self.restore()

    def make_label(self, text, name=None):
        label = QLabel(text)
        if name:
            label.setObjectName(name)
        return label

    def build(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)

        top = QFrame(); top.setObjectName("top")
        tl = QHBoxLayout(top); tl.setContentsMargins(28, 20, 28, 18)
        brand = QVBoxLayout()
        brand.addWidget(self.make_label("DJAR RVC Studio", "title"))
        brand.addWidget(self.make_label("Professional local voice conversion workstation", "subtitle"))
        tl.addLayout(brand); tl.addStretch()
        self.badge = self.make_label("●  RVC OFFLINE", "offline")
        tl.addWidget(self.badge)
        outer.addWidget(top)

        api = QFrame()
        al = QHBoxLayout(api); al.setContentsMargins(28, 12, 28, 12)
        al.addWidget(QLabel("RVC API"))
        self.api = QLineEdit(DEFAULT_API); self.api.setPlaceholderText(DEFAULT_API)
        al.addWidget(self.api, 1)
        self.test_btn = QPushButton("Test Connection"); self.test_btn.clicked.connect(self.test_connection)
        al.addWidget(self.test_btn)
        outer.addWidget(api)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget(); cl = QVBoxLayout(content); cl.setContentsMargins(28, 10, 28, 28); cl.setSpacing(16)
        scroll.setWidget(content); outer.addWidget(scroll, 1)

        grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(16); grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1); cl.addLayout(grid)

        left = self.card("VOICE & AUDIO"); ll = left.layout()
        ll.addWidget(self.make_label("Voice model", "section"))
        vr = QHBoxLayout()
        self.voice = QComboBox(); self.voice.addItem("Voice / Speaker ID 0", "0")
        vr.addWidget(self.voice, 1)
        self.refresh_btn = QPushButton("↻  Refresh"); self.refresh_btn.clicked.connect(self.refresh_voices); vr.addWidget(self.refresh_btn)
        ll.addLayout(vr)
        ll.addSpacing(7); ll.addWidget(self.make_label("Input audio", "section"))
        drop = QFrame(); drop.setObjectName("drop")
        dl = QVBoxLayout(drop); dl.setContentsMargins(18, 20, 18, 20)
        self.audio_name = self.make_label("🎵  No audio selected", "muted"); self.audio_name.setAlignment(Qt.AlignCenter); dl.addWidget(self.audio_name)
        b = QPushButton("Browse audio file"); b.clicked.connect(self.pick_audio); dl.addWidget(b)
        ll.addWidget(drop)
        self.audio_path = QLineEdit(); self.audio_path.hide(); ll.addWidget(self.audio_path)
        ll.addSpacing(7); ll.addWidget(self.make_label("F0 algorithm", "section"))
        self.f0 = QComboBox(); self.f0.addItems(["RMVPE", "CREPE", "Harvest", "PM"]); ll.addWidget(self.f0)
        grid.addWidget(left, 0, 0)

        right = self.card("VOICE CONTROL"); rl = right.layout()
        self.pitch = self.slider(rl, "Pitch / Transpose", -12, 12, 0, " semitones")
        self.index_rate = self.slider(rl, "Index / Feature ratio", 0, 100, 75, "%")
        self.protect = self.slider(rl, "Protect breath / consonants", 0, 50, 33, "%")
        rl.addSpacing(3); rl.addWidget(self.make_label("ADVANCED SETTINGS", "section"))
        self.filter_radius = self.slider(rl, "Median filter radius", 0, 7, 3, "")
        self.resample = self.slider(rl, "Resample rate", 0, 48000, 0, " Hz")
        self.rms = self.slider(rl, "Volume envelope mix", 0, 100, 25, "%")
        rl.addWidget(self.make_label("Feature index", "section"))
        ir = QHBoxLayout(); self.index_path = QLineEdit(); self.index_path.setPlaceholderText("Optional .index file"); ir.addWidget(self.index_path, 1)
        ib = QPushButton("Browse"); ib.clicked.connect(self.pick_index); ir.addWidget(ib); rl.addLayout(ir)
        grid.addWidget(right, 0, 1)

        conv = self.card("CONVERSION"); cv = conv.layout()
        sr = QHBoxLayout(); self.status = self.make_label("Ready", "muted"); sr.addWidget(self.status); sr.addStretch(); self.percent = self.make_label("0%", "value"); sr.addWidget(self.percent); cv.addLayout(sr)
        self.progress = QProgressBar(); self.progress.setValue(0); cv.addWidget(self.progress)
        br = QHBoxLayout(); self.convert_btn = QPushButton("✦  CONVERT AUDIO"); self.convert_btn.setObjectName("primary"); self.convert_btn.clicked.connect(self.convert); br.addWidget(self.convert_btn, 2)
        ob = QPushButton("Open Output"); ob.clicked.connect(self.open_output); br.addWidget(ob, 1); cv.addLayout(br)
        cl.addWidget(conv)
        cl.addWidget(self.make_label("RVC remains local on this Windows PC. Converted files are saved in DJAR_RVC_Output beside the source audio.", "muted"))

    def card(self, title):
        frame = QFrame(); frame.setObjectName("card")
        layout = QVBoxLayout(frame); layout.setContentsMargins(20, 18, 20, 20); layout.setSpacing(9)
        layout.addWidget(self.make_label(title, "section")); return frame

    def slider(self, layout, label, lo, hi, value, suffix):
        box = QVBoxLayout(); head = QHBoxLayout(); head.addWidget(QLabel(label)); head.addStretch()
        value_label = self.make_label(f"{value}{suffix}", "value"); head.addWidget(value_label); box.addLayout(head)
        s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(value)
        s.valueChanged.connect(lambda v, out=value_label, suf=suffix: out.setText(f"{v}{suf}")); box.addWidget(s); layout.addLayout(box); return s

    def restore(self):
        self.api.setText(self.saved.get("api", DEFAULT_API)); self.f0.setCurrentIndex(self.saved.get("f0", 0))
        for widget, key, default in [(self.pitch,"pitch",0),(self.index_rate,"index_rate",75),(self.protect,"protect",33),(self.filter_radius,"filter",3),(self.resample,"resample",0),(self.rms,"rms",25)]:
            widget.setValue(self.saved.get(key, default))

    def save(self):
        save_settings({"api":self.api.text().strip(),"f0":self.f0.currentIndex(),"pitch":self.pitch.value(),"index_rate":self.index_rate.value(),"protect":self.protect.value(),"filter":self.filter_radius.value(),"resample":self.resample.value(),"rms":self.rms.value()})

    def api_url(self, endpoint): return self.api.text().strip().rstrip("/") + endpoint

    def run(self, fn, done, progress=False):
        self.thread = QThread(self); worker = Worker(fn); worker.moveToThread(self.thread); self.thread.started.connect(worker.run)
        worker.finished.connect(done); worker.failed.connect(self.failed)
        if progress: worker.progress.connect(self.update_progress)
        worker.finished.connect(self.thread.quit); worker.failed.connect(self.thread.quit); worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()

    def test_connection(self):
        self.status.setText("Testing RVC API…"); self.test_btn.setEnabled(False)
        def fn(p):
            r=requests.post(self.api_url("/run/infer_clean"),json={"data":[]},timeout=15); r.raise_for_status(); return True
        def done(_):
            self.test_btn.setEnabled(True); self.badge.setText("●  RVC CONNECTED"); self.badge.setObjectName("online"); self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge); self.status.setText("Connected to RVC API")
        self.run(fn, done)

    def refresh_voices(self):
        self.status.setText("Refreshing voice list…")
        def fn(p):
            r=requests.post(self.api_url("/run/infer_refresh"),json={"data":[]},timeout=30); r.raise_for_status(); return r.json().get("data",[])
        def done(data):
            self.voice.clear(); vals=[str(x) for x in data] if isinstance(data,list) else []
            if not vals: vals=["Voice / Speaker ID 0"]
            for i, name in enumerate(vals): self.voice.addItem(name, str(i))
            self.status.setText(f"Voice list refreshed · {len(vals)} option(s)")
        self.run(fn, done)

    def pick_audio(self):
        path,_=QFileDialog.getOpenFileName(self,"Select audio","","Audio files (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*.*)")
        if path: self.audio_path.setText(path); self.audio_name.setText("🎵  " + Path(path).name); self.audio_name.setObjectName("value"); self.audio_name.style().unpolish(self.audio_name); self.audio_name.style().polish(self.audio_name)

    def pick_index(self):
        path,_=QFileDialog.getOpenFileName(self,"Select feature index","","Index files (*.index);;All files (*.*)")
        if path: self.index_path.setText(path)

    def convert(self):
        audio=self.audio_path.text().strip()
        if not audio or not os.path.isfile(audio): QMessageBox.warning(self,"Input required","Please select a valid audio file first."); return
        self.save(); self.set_busy(True); self.update_progress(5,"Preparing conversion…")
        def fn(progress):
            progress.emit(15,"Sending request to RVC…")
            empty={"name":"none.txt","data":"data:text/plain;base64,"+base64.b64encode(b"").decode()}
            vid=self.voice.currentData() or "0"
            payload={"data":[int(float(vid)),audio,self.pitch.value(),empty,self.f0.currentText().lower(),self.index_path.text().strip(),"",self.index_rate.value()/100.0,self.filter_radius.value(),self.resample.value(),self.rms.value()/100.0,self.protect.value()/100.0]}
            progress.emit(25,"RVC is processing…")
            r=requests.post(self.api_url("/run/infer_convert"),json=payload,timeout=3600); r.raise_for_status(); obj=r.json(); data=obj.get("data",[]); ao=data[1] if len(data)>1 else None
            if not isinstance(ao,dict) or "data" not in ao: raise RuntimeError("RVC returned no converted audio data.")
            raw=ao["data"].split(",",1)[-1]; out_dir=Path(audio).parent/"DJAR_RVC_Output"; out_dir.mkdir(exist_ok=True); out=out_dir/(Path(audio).stem+"_RVC.wav"); out.write_bytes(base64.b64decode(raw)); progress.emit(100,"Conversion complete"); return str(out)
        self.run(fn, self.convert_done, True)

    def convert_done(self,out):
        self.set_busy(False); self.last_output=out; self.update_progress(100,"✓ Conversion complete"); QMessageBox.information(self,"Conversion complete","Your converted audio is ready.\n\n"+out)

    def update_progress(self,value,msg): self.progress.setValue(int(value)); self.percent.setText(f"{int(value)}%"); self.status.setText(msg)

    def failed(self,msg): self.set_busy(False); self.progress.setValue(0); self.percent.setText("0%"); self.status.setText("✕ Operation failed"); QMessageBox.critical(self,"RVC Error",msg)

    def set_busy(self,busy): self.convert_btn.setEnabled(not busy); self.refresh_btn.setEnabled(not busy); self.test_btn.setEnabled(not busy)

    def open_output(self):
        audio=self.audio_path.text().strip(); target=Path(self.last_output if self.last_output else (Path(audio).parent/"DJAR_RVC_Output" if audio else ""))
        if not str(target): return
        if target.is_file(): target=target.parent
        target.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def closeEvent(self,event): self.save(); event.accept()


if __name__ == "__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_TITLE); app.setFont(QFont("Segoe UI",10)); window=App(); window.show(); sys.exit(app.exec())
