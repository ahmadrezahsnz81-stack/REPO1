import base64
import json
import os
import sys
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from PySide6.QtCore import QObject, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QComboBox, QScrollArea, QSlider, QVBoxLayout, QWidget
)

APP_TITLE = "DJAR RVC Studio"
DEFAULT_API = "http://127.0.0.1:7897"
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "DJAR RVC Studio"
CONFIG_FILE = CONFIG_DIR / "settings.json"

STYLE = """
QMainWindow,QWidget{background:#090c11;color:#e9edf5;font-family:'Segoe UI';font-size:10pt}
QFrame#top{background:#0d1118;border-bottom:1px solid #242c37}
QFrame#card{background:#121821;border:1px solid #273140;border-radius:14px}
QFrame#drop{background:#0c121a;border:1px dashed #3e4c5e;border-radius:12px}
QFrame#analysis{background:#101722;border:1px solid #293444;border-radius:10px}
QLabel#title{font-size:25pt;font-weight:700;color:#fff}
QLabel#subtitle,QLabel#muted{color:#8995a8}
QLabel#section{font-size:11pt;font-weight:700;color:#f5f7fb}
QLabel#value{font-weight:700;color:#e1e7f0}
QLabel#online{font-weight:700;color:#61e88d}
QLabel#offline{font-weight:700;color:#ff7181}
QLabel#analyze{color:#b8c3d4}
QLineEdit,QComboBox{background:#0a1017;color:#e9edf5;border:1px solid #2c3746;border-radius:8px;padding:9px 10px}
QLineEdit:focus,QComboBox:focus{border:1px solid #717cff}
QComboBox QAbstractItemView{background:#111822;color:#fff;selection-background-color:#343f78}
QPushButton{background:#19222e;color:#e9edf5;border:1px solid #334052;border-radius:8px;padding:9px 14px;font-weight:600}
QPushButton:hover{background:#242f3d;border-color:#4b5a70}
QPushButton#primary{background:#6975ff;color:white;border:1px solid #818aff;padding:13px;font-size:11pt;font-weight:700}
QPushButton#primary:hover{background:#7a85ff}
QPushButton#analyzeBtn{background:#18263a;border:1px solid #405a7d;color:#dbe9ff;padding:11px;font-size:10.5pt;font-weight:700}
QPushButton#analyzeBtn:hover{background:#20334d}
QProgressBar{background:#0a0f15;border:0;border-radius:5px;height:9px;text-align:center;color:transparent}
QProgressBar::chunk{background:#6975ff;border-radius:5px}
QSlider::groove:horizontal{height:4px;background:#293440;border-radius:2px}
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
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def analyze_audio(path):
    """Lightweight local vocal analysis. It never sends audio to the internet."""
    data, sr = sf.read(path, always_2d=False, dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    data = np.asarray(data, dtype=np.float32)
    if data.size == 0:
        raise ValueError("The selected audio file is empty.")
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data * data) + 1e-12))
    duration = len(data) / float(sr)
    # Downsample analysis to keep the GUI fast.
    step = max(1, len(data) // 250000)
    x = data[::step]
    zcr = float(np.mean(np.abs(np.diff(np.signbit(x).astype(np.int8))))) if len(x) > 1 else 0.0

    # Autocorrelation pitch estimate over speech-friendly frames.
    frame = min(len(data), int(sr * 0.06))
    hop = max(1, int(sr * 0.03))
    f0_values = []
    if frame >= 512:
        for start in range(0, len(data) - frame + 1, hop):
            y = data[start:start + frame]
            energy = float(np.sqrt(np.mean(y * y) + 1e-12))
            if energy < max(0.008, rms * 0.12):
                continue
            y = y - np.mean(y)
            corr = np.correlate(y, y, mode="full")[frame - 1:]
            min_lag = max(1, int(sr / 1000.0))
            max_lag = min(frame - 1, int(sr / 60.0))
            if max_lag <= min_lag:
                continue
            segment = corr[min_lag:max_lag + 1]
            lag = int(np.argmax(segment)) + min_lag
            if corr[lag] > 0.18 * corr[0]:
                f0_values.append(sr / lag)
            if len(f0_values) >= 250:
                break
    median_f0 = float(np.median(f0_values)) if f0_values else 0.0
    voiced_ratio = len(f0_values) / max(1, min(250, max(1, (len(data) - frame) // hop + 1)))
    clipping = peak >= 0.98

    # Conservative optimization heuristics. Transpose stays 0 because the target
    # RVC model's trained pitch range is not knowable from the source audio alone.
    if zcr > 0.16 or voiced_ratio < 0.22:
        protect = 40
        index_rate = 60
        median_filter = 5
    elif zcr > 0.10:
        protect = 35
        index_rate = 68
        median_filter = 3
    else:
        protect = 30
        index_rate = 75
        median_filter = 3
    rms_percent = int(np.clip(22 + (0.16 - rms) * 35, 15, 30))
    return {
        "sample_rate": int(sr),
        "duration": duration,
        "peak": peak,
        "rms": rms,
        "zcr": zcr,
        "median_f0": median_f0,
        "voiced_ratio": voiced_ratio,
        "clipping": clipping,
        "protect": protect,
        "index_rate": index_rate,
        "median_filter": median_filter,
        "rms_mix": rms_percent,
    }


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
        self.resize(1180, 860)
        self.setMinimumSize(980, 700)
        self.setStyleSheet(STYLE)
        self.saved = load_settings()
        self.last_output = ""
        self.thread = None
        self.build()
        self.restore()

    def label(self, text, obj=None):
        x = QLabel(text)
        if obj:
            x.setObjectName(obj)
        return x

    def build(self):
        root = QWidget(); outer = QVBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0); self.setCentralWidget(root)
        top = QFrame(); top.setObjectName("top"); tl = QHBoxLayout(top); tl.setContentsMargins(28,18,28,16)
        brand = QVBoxLayout(); brand.addWidget(self.label("DJAR RVC Studio","title")); brand.addWidget(self.label("Professional local voice conversion workstation","subtitle")); tl.addLayout(brand); tl.addStretch()
        self.badge = self.label("●  RVC OFFLINE","offline"); tl.addWidget(self.badge); outer.addWidget(top)

        api = QFrame(); al = QHBoxLayout(api); al.setContentsMargins(28,10,28,10); al.addWidget(QLabel("RVC API")); self.api = QLineEdit(DEFAULT_API); al.addWidget(self.api,1)
        self.test_btn = QPushButton("Test Connection"); self.test_btn.clicked.connect(self.test_connection); al.addWidget(self.test_btn); outer.addWidget(api)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); content = QWidget(); cl = QVBoxLayout(content); cl.setContentsMargins(28,8,28,28); cl.setSpacing(14); scroll.setWidget(content); outer.addWidget(scroll,1)
        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(14); grid.setColumnStretch(0,1); grid.setColumnStretch(1,1); cl.addLayout(grid)

        left = self.card("VOICE & AUDIO"); ll=left.layout(); ll.addWidget(self.label("Voice model","section")); vr=QHBoxLayout(); self.voice=QComboBox(); self.voice.addItem("Voice / Speaker ID 0","0"); vr.addWidget(self.voice,1); self.refresh_btn=QPushButton("↻  Refresh"); self.refresh_btn.clicked.connect(self.refresh_voices); vr.addWidget(self.refresh_btn); ll.addLayout(vr)
        ll.addSpacing(5); ll.addWidget(self.label("Input audio","section")); drop=QFrame(); drop.setObjectName("drop"); dl=QVBoxLayout(drop); dl.setContentsMargins(16,16,16,16); self.audio_name=self.label("🎵  No audio selected","muted"); self.audio_name.setAlignment(Qt.AlignCenter); dl.addWidget(self.audio_name); bb=QPushButton("Browse audio file"); bb.clicked.connect(self.pick_audio); dl.addWidget(bb); ll.addWidget(drop); self.audio_path=QLineEdit(); self.audio_path.hide(); ll.addWidget(self.audio_path)
        ll.addSpacing(5); ll.addWidget(self.label("F0 algorithm","section")); self.f0=QComboBox(); self.f0.addItems(["RMVPE","CREPE","Harvest","PM"]); ll.addWidget(self.f0)
        grid.addWidget(left,0,0)

        right=self.card("VOICE CONTROL"); rl=right.layout(); self.pitch=self.slider(rl,"Pitch / Transpose",-12,12,0," semitones"); self.index_rate=self.slider(rl,"Index / Feature ratio",0,100,75,"%"); self.protect=self.slider(rl,"Protect breath / consonants",0,50,33,"%"); rl.addSpacing(2); rl.addWidget(self.label("ADVANCED SETTINGS","section")); self.filter_radius=self.slider(rl,"Median filter radius",0,7,3,""); self.resample=self.slider(rl,"Resample rate",0,48000,0," Hz"); self.rms=self.slider(rl,"Volume envelope mix",0,100,25,"%"); rl.addWidget(self.label("Feature index","section")); ir=QHBoxLayout(); self.index_path=QLineEdit(); self.index_path.setPlaceholderText("Optional .index file"); ir.addWidget(self.index_path,1); ib=QPushButton("Browse"); ib.clicked.connect(self.pick_index); ir.addWidget(ib); rl.addLayout(ir); grid.addWidget(right,0,1)

        analyze=self.card("VOCAL ANALYZER"); av=analyze.layout(); ar=QHBoxLayout(); self.analyze_btn=QPushButton("✦  ANALYZE VOCAL & AUTO-OPTIMIZE"); self.analyze_btn.setObjectName("analyzeBtn"); self.analyze_btn.clicked.connect(self.analyze); ar.addWidget(self.analyze_btn,2); ar.addWidget(self.label("Local analysis · audio is not uploaded","muted"),1); av.addLayout(ar)
        self.analysis_box=QFrame(); self.analysis_box.setObjectName("analysis"); ax=QGridLayout(self.analysis_box); ax.setContentsMargins(14,12,14,12)
        self.a_pitch=self.analysis_value(ax,"Detected pitch",0,0); self.a_duration=self.analysis_value(ax,"Duration",0,2); self.a_sr=self.analysis_value(ax,"Sample rate",1,0); self.a_quality=self.analysis_value(ax,"Voice quality",1,2); self.a_reco=self.label("Run analysis to receive recommended RVC settings.","analyze"); self.a_reco.setWordWrap(True); ax.addWidget(self.a_reco,2,0,1,4); av.addWidget(self.analysis_box); cl.addWidget(analyze)

        conv=self.card("CONVERSION"); cv=conv.layout(); sr=QHBoxLayout(); self.status=self.label("Ready","muted"); sr.addWidget(self.status); sr.addStretch(); self.percent=self.label("0%","value"); sr.addWidget(self.percent); cv.addLayout(sr); self.progress=QProgressBar(); self.progress.setValue(0); cv.addWidget(self.progress); br=QHBoxLayout(); self.convert_btn=QPushButton("✦  CONVERT AUDIO"); self.convert_btn.setObjectName("primary"); self.convert_btn.clicked.connect(self.convert); br.addWidget(self.convert_btn,2); ob=QPushButton("Open Output"); ob.clicked.connect(self.open_output); br.addWidget(ob,1); cv.addLayout(br); cl.addWidget(conv); cl.addWidget(self.label("RVC stays local on this PC. Output is saved in DJAR_RVC_Output beside the source file.","muted"))

    def card(self,title):
        f=QFrame(); f.setObjectName("card"); l=QVBoxLayout(f); l.setContentsMargins(20,17,20,20); l.setSpacing(8); l.addWidget(self.label(title,"section")); return f

    def slider(self,layout,label,lo,hi,value,suffix):
        box=QVBoxLayout(); h=QHBoxLayout(); h.addWidget(QLabel(label)); h.addStretch(); v=self.label(f"{value}{suffix}","value"); h.addWidget(v); box.addLayout(h); s=QSlider(Qt.Horizontal); s.setRange(lo,hi); s.setValue(value); s.valueChanged.connect(lambda n,out=v,suf=suffix: out.setText(f"{n}{suf}")); box.addWidget(s); layout.addLayout(box); return s

    def analysis_value(self,layout,name,row,col):
        box=QVBoxLayout(); box.addWidget(self.label(name,"muted")); val=self.label("—","value"); box.addWidget(val); layout.addLayout(box,row,col); return val

    def restore(self):
        self.api.setText(self.saved.get("api",DEFAULT_API)); self.f0.setCurrentIndex(self.saved.get("f0",0))
        for w,k,d in [(self.pitch,"pitch",0),(self.index_rate,"index_rate",75),(self.protect,"protect",33),(self.filter_radius,"filter",3),(self.resample,"resample",0),(self.rms,"rms",25)]: w.setValue(self.saved.get(k,d))

    def save(self):
        save_settings({"api":self.api.text().strip(),"f0":self.f0.currentIndex(),"pitch":self.pitch.value(),"index_rate":self.index_rate.value(),"protect":self.protect.value(),"filter":self.filter_radius.value(),"resample":self.resample.value(),"rms":self.rms.value()})

    def api_url(self,path): return self.api.text().strip().rstrip("/")+path

    def run(self,fn,done,progress=False):
        self.thread=QThread(self); worker=Worker(fn); worker.moveToThread(self.thread); self.thread.started.connect(worker.run); worker.finished.connect(done); worker.failed.connect(self.failed)
        if progress: worker.progress.connect(self.update_progress)
        worker.finished.connect(self.thread.quit); worker.failed.connect(self.thread.quit); worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()

    def test_connection(self):
        # Do NOT call infer_clean here: that endpoint is an RVC UI state/action endpoint,
        # not a health endpoint, and can remain busy. A lightweight GET to the WebUI root
        # is enough to prove that the local RVC server is reachable.
        self.status.setText("Checking RVC WebUI…"); self.test_btn.setEnabled(False)
        def fn(p):
            r=requests.get(self.api.text().strip().rstrip("/"),timeout=5); r.raise_for_status(); return r.status_code
        def done(code):
            self.test_btn.setEnabled(True); self.badge.setText("●  RVC CONNECTED"); self.badge.setObjectName("online"); self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge); self.status.setText(f"RVC WebUI reachable · HTTP {code}")
        self.run(fn,done)

    def refresh_voices(self):
        self.status.setText("Refreshing voice list…"); self.refresh_btn.setEnabled(False)
        def fn(p):
            r=requests.post(self.api_url("/run/infer_refresh"),json={"data":[]},timeout=90); r.raise_for_status(); return r.json().get("data",[])
        def done(data):
            self.refresh_btn.setEnabled(True); self.voice.clear(); vals=[str(x) for x in data] if isinstance(data,list) else []
            if not vals: vals=["Voice / Speaker ID 0"]
            for i,name in enumerate(vals): self.voice.addItem(name,str(i))
            self.status.setText(f"Voice list refreshed · {len(vals)} option(s)")
        self.run(fn,done)

    def pick_audio(self):
        path,_=QFileDialog.getOpenFileName(self,"Select audio","","Audio files (*.wav *.flac *.ogg *.mp3 *.m4a);;All files (*.*)")
        if path: self.audio_path.setText(path); self.audio_name.setText("🎵  "+Path(path).name); self.audio_name.setObjectName("value"); self.audio_name.style().unpolish(self.audio_name); self.audio_name.style().polish(self.audio_name)

    def pick_index(self):
        path,_=QFileDialog.getOpenFileName(self,"Select feature index","","Index files (*.index);;All files (*.*)")
        if path: self.index_path.setText(path)

    def analyze(self):
        audio=self.audio_path.text().strip()
        if not audio or not os.path.isfile(audio): QMessageBox.warning(self,"Input required","Please select an audio file first."); return
        self.analyze_btn.setEnabled(False); self.status.setText("Analyzing vocal locally…")
        def fn(p): p.emit(10,"Reading audio…"); result=analyze_audio(audio); p.emit(100,"Analysis complete"); return result
        self.run(fn,self.analysis_done,True)

    def analysis_done(self,r):
        self.analyze_btn.setEnabled(True); self.pitch.setValue(0); self.index_rate.setValue(r["index_rate"]); self.protect.setValue(r["protect"]); self.filter_radius.setValue(r["median_filter"]); self.resample.setValue(0); self.rms.setValue(r["rms_mix"]); self.f0.setCurrentIndex(0)
        pitch=f'{r["median_f0"]:.0f} Hz' if r["median_f0"] else "Not confidently detected"
        quality="Clean / stable" if r["voiced_ratio"]>=0.45 and not r["clipping"] else ("Moderate / breathy" if r["voiced_ratio"]>=0.22 else "Noisy / low voiced ratio")
        self.a_pitch.setText(pitch); self.a_duration.setText(f'{r["duration"]:.1f} s'); self.a_sr.setText(f'{r["sample_rate"]} Hz'); self.a_quality.setText(quality)
        clip=" · clipping detected" if r["clipping"] else ""
        self.a_reco.setText(f'Applied profile: RMVPE · Index {r["index_rate"]}% · Protect {r["protect"]}% · Median {r["median_filter"]} · Volume mix {r["rms_mix"]}% · Transpose 0{clip}. Transpose is kept at 0 because the target model range cannot be inferred safely from source audio alone.')
        self.save(); self.progress.setValue(100); self.percent.setText("100%")

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
        self.run(fn,self.convert_done,True)

    def convert_done(self,out): self.set_busy(False); self.last_output=out; self.update_progress(100,"✓ Conversion complete"); QMessageBox.information(self,"Conversion complete","Your converted audio is ready.\n\n"+out)
    def update_progress(self,v,msg): self.progress.setValue(int(v)); self.percent.setText(f"{int(v)}%"); self.status.setText(msg)
    def failed(self,msg): self.set_busy(False); self.analyze_btn.setEnabled(True); self.progress.setValue(0); self.percent.setText("0%"); self.status.setText("✕ Operation failed"); self.badge.setText("●  RVC OFFLINE"); self.badge.setObjectName("offline"); self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge); QMessageBox.critical(self,"RVC Error",msg)
    def set_busy(self,busy): self.convert_btn.setEnabled(not busy); self.refresh_btn.setEnabled(not busy); self.test_btn.setEnabled(not busy); self.analyze_btn.setEnabled(not busy)
    def open_output(self):
        audio=self.audio_path.text().strip(); target=Path(self.last_output if self.last_output else (Path(audio).parent/"DJAR_RVC_Output" if audio else ""))
        if not str(target): return
        if target.is_file(): target=target.parent
        target.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
    def closeEvent(self,event): self.save(); event.accept()


if __name__=="__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_TITLE); app.setFont(QFont("Segoe UI",10)); w=App(); w.show(); sys.exit(app.exec())
