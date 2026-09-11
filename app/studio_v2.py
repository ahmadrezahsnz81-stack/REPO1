import base64
import json
import os
import socket
import sys
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from PySide6.QtCore import QObject, Qt, QThread, Signal, QTimer, QUrl
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
QLabel#title{font-size:25pt;font-weight:700;color:#fff;background:transparent}
QLabel#subtitle,QLabel#muted{color:#8995a8;background:transparent}
QLabel#section{font-size:11pt;font-weight:700;color:#f5f7fb;background:transparent}
QLabel#value{font-weight:700;color:#e1e7f0;background:transparent}
QLabel#online{font-weight:700;color:#61e88d;background:transparent}
QLabel#offline{font-weight:700;color:#ff7181;background:transparent}
QLabel#checking{font-weight:700;color:#f0c96b;background:transparent}
QLabel#error{font-weight:700;color:#ff8c99;background:transparent}
QLabel#analyze{color:#b8c3d4;background:transparent}
QLineEdit,QComboBox{background:#0a1017;color:#e9edf5;border:1px solid #2c3746;border-radius:8px;padding:9px 10px}
QLineEdit:focus,QComboBox:focus{border:1px solid #717cff}
QComboBox QAbstractItemView{background:#111822;color:#fff;selection-background-color:#343f78}
QPushButton{background:#19222e;color:#e9edf5;border:1px solid #334052;border-radius:8px;padding:9px 14px;font-weight:600}
QPushButton:hover{background:#242f3d;border-color:#4b5a70}
QPushButton:pressed{background:#151d27}
QPushButton#primary{background:#6975ff;color:white;border:1px solid #818aff;padding:13px;font-size:11pt;font-weight:700}
QPushButton#primary:hover{background:#7a85ff}
QPushButton#analyzeBtn{background:#18263a;border:1px solid #405a7d;color:#dbe9ff;padding:11px;font-size:10.5pt;font-weight:700}
QPushButton#analyzeBtn:hover{background:#20334d}
QProgressBar{background:#0a0f15;border:0;border-radius:5px;height:9px;text-align:center;color:transparent}
QProgressBar::chunk{background:#6975ff;border-radius:5px}
QSlider::groove:horizontal{height:4px;background:#293440;border-radius:2px}
QSlider::sub-page:horizontal{background:#6975ff;border-radius:2px}
QSlider::handle:horizontal{width:16px;height:16px;margin:-6px 0;background:#edf1f7;border-radius:8px}
QScrollArea{border:0;background:transparent}
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


def analyze_audio(path, progress=None):
    """Fast local analysis. It never uploads the source audio."""
    if progress:
        progress.emit(10, "Reading audio locally…")
    data, sr = sf.read(path, always_2d=False, dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    data = np.asarray(data, dtype=np.float32)
    if data.size == 0:
        raise ValueError("The selected audio file is empty.")

    # Downsample only for cheap quality measurements.
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data * data) + 1e-12))
    duration = len(data) / float(sr)
    qstep = max(1, len(data) // 120000)
    x = data[::qstep]
    zcr = float(np.mean(np.abs(np.diff(np.signbit(x).astype(np.int8))))) if len(x) > 1 else 0.0

    if progress:
        progress.emit(35, "Estimating vocal pitch…")

    # Sample at most 20 short frames across the first 30 seconds.
    analysis_len = min(len(data), int(sr * 30))
    frame = min(analysis_len, max(512, int(sr * 0.05)))
    if frame > analysis_len:
        frame = analysis_len
    if frame >= 512:
        positions = np.linspace(0, max(0, analysis_len - frame), num=min(20, max(1, analysis_len // max(1, int(sr * 0.4)))), dtype=int)
    else:
        positions = []
    f0_values = []
    for i, start in enumerate(positions):
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
        lag = int(np.argmax(corr[min_lag:max_lag + 1])) + min_lag
        if corr[lag] > 0.18 * corr[0]:
            f0_values.append(sr / lag)
        if progress:
            progress.emit(35 + int(30 * (i + 1) / max(1, len(positions))), "Estimating vocal pitch…")

    median_f0 = float(np.median(f0_values)) if f0_values else 0.0
    voiced_ratio = len(f0_values) / max(1, len(positions))

    if zcr > 0.16 or voiced_ratio < 0.22:
        protect, index_rate, median_filter = 40, 60, 5
        quality = "Noisy / unstable"
    elif zcr > 0.10:
        protect, index_rate, median_filter = 35, 68, 3
        quality = "Moderate / usable"
    else:
        protect, index_rate, median_filter = 30, 75, 3
        quality = "Clean / stable"

    rms_percent = int(np.clip(22 + (0.16 - rms) * 35, 15, 30))
    if peak >= 0.98:
        quality += " · clipping detected"
    if progress:
        progress.emit(100, "Analysis complete")

    return {
        "sample_rate": int(sr), "duration": duration, "peak": peak,
        "rms": rms, "zcr": zcr, "median_f0": median_f0,
        "voiced_ratio": voiced_ratio, "protect": protect,
        "index_rate": index_rate, "median_filter": median_filter,
        "rms_mix": rms_percent, "quality": quality,
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
        self.setMinimumSize(720, 640)
        self.setStyleSheet(STYLE)
        self.saved = load_settings()
        self.last_output = ""
        self.thread = None
        self.single_column = False
        self.active_voice = ""
        self.active_spk = 0
        self.active_index = ""
        self.build()
        self.restore()
        QTimer.singleShot(350, self.test_connection)

    def label(self, text, obj=None):
        x = QLabel(text)
        if obj:
            x.setObjectName(obj)
        return x

    def build(self):
        root = QWidget(); outer = QVBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0); self.setCentralWidget(root)
        top = QFrame(); top.setObjectName("top"); tl = QHBoxLayout(top); tl.setContentsMargins(24,16,24,14)
        brand = QVBoxLayout(); brand.addWidget(self.label("DJAR RVC Studio","title")); brand.addWidget(self.label("Professional local voice conversion workstation","subtitle")); tl.addLayout(brand); tl.addStretch()
        self.badge = self.label("●  RVC OFFLINE","offline"); tl.addWidget(self.badge); outer.addWidget(top)

        api = QFrame(); al=QHBoxLayout(api); al.setContentsMargins(24,9,24,9); al.addWidget(QLabel("RVC API")); self.api=QLineEdit(DEFAULT_API); al.addWidget(self.api,1); self.test_btn=QPushButton("Test Connection"); self.test_btn.clicked.connect(self.test_connection); al.addWidget(self.test_btn); outer.addWidget(api)
        self.api.textChanged.connect(lambda: self.set_badge("●  RVC OFFLINE","offline"))

        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); content=QWidget(); self.cl=QVBoxLayout(content); self.cl.setContentsMargins(24,8,24,24); self.cl.setSpacing(14); self.scroll.setWidget(content); outer.addWidget(self.scroll,1)
        self.grid=QGridLayout(); self.grid.setHorizontalSpacing(14); self.grid.setVerticalSpacing(14); self.grid.setColumnStretch(0,1); self.grid.setColumnStretch(1,1); self.cl.addLayout(self.grid)

        self.left=self.card("VOICE & AUDIO"); ll=self.left.layout(); ll.addWidget(self.label("Voice model","section")); vr=QHBoxLayout(); self.voice=QComboBox(); self.voice.addItem("Voice / Speaker ID 0","0"); self.voice.currentIndexChanged.connect(self.voice_changed); vr.addWidget(self.voice,1); self.refresh_btn=QPushButton("↻  Refresh"); self.refresh_btn.clicked.connect(self.refresh_voices); vr.addWidget(self.refresh_btn); ll.addLayout(vr)
        ll.addSpacing(5); ll.addWidget(self.label("Input audio","section")); drop=QFrame(); drop.setObjectName("drop"); dl=QVBoxLayout(drop); dl.setContentsMargins(16,16,16,16); self.audio_name=self.label("🎵  No audio selected","muted"); self.audio_name.setAlignment(Qt.AlignCenter); dl.addWidget(self.audio_name); bb=QPushButton("Browse audio file"); bb.clicked.connect(self.pick_audio); dl.addWidget(bb); ll.addWidget(drop); self.audio_path=QLineEdit(); self.audio_path.hide(); ll.addWidget(self.audio_path)
        ll.addSpacing(5); ll.addWidget(self.label("F0 algorithm","section")); self.f0=QComboBox(); self.f0.addItems(["RMVPE","CREPE","Harvest","PM"]); ll.addWidget(self.f0); self.grid.addWidget(self.left,0,0)

        self.right=self.card("VOICE CONTROL"); rl=self.right.layout(); self.pitch=self.slider(rl,"Pitch / Transpose",-12,12,0," semitones"); self.index_rate=self.slider(rl,"Index / Feature ratio",0,100,75,"%"); self.protect=self.slider(rl,"Protect breath / consonants",0,50,33,"%"); rl.addSpacing(2); rl.addWidget(self.label("ADVANCED SETTINGS","section")); self.filter_radius=self.slider(rl,"Median filter radius",0,7,3,""); self.resample=self.slider(rl,"Resample rate",0,48000,0," Hz"); self.rms=self.slider(rl,"Volume envelope mix",0,100,25,"%"); rl.addWidget(self.label("Feature index","section")); ir=QHBoxLayout(); self.index_path=QLineEdit(); self.index_path.setPlaceholderText("Optional .index file"); ir.addWidget(self.index_path,1); ib=QPushButton("Browse"); ib.clicked.connect(self.pick_index); ir.addWidget(ib); rl.addLayout(ir); self.grid.addWidget(self.right,0,1)

        analyze=self.card("VOCAL ANALYZER"); av=analyze.layout(); ar=QHBoxLayout(); self.analyze_btn=QPushButton("✦  ANALYZE VOCAL & AUTO-OPTIMIZE"); self.analyze_btn.setObjectName("analyzeBtn"); self.analyze_btn.clicked.connect(self.analyze); ar.addWidget(self.analyze_btn,2); self.analysis_status=self.label("Local analysis · audio is not uploaded","muted"); ar.addWidget(self.analysis_status,1); av.addLayout(ar)
        self.analysis_box=QFrame(); self.analysis_box.setObjectName("analysis"); ax=QGridLayout(self.analysis_box); ax.setContentsMargins(14,12,14,12); self.a_pitch=self.analysis_value(ax,"Detected pitch",0,0); self.a_duration=self.analysis_value(ax,"Duration",0,2); self.a_sr=self.analysis_value(ax,"Sample rate",1,0); self.a_quality=self.analysis_value(ax,"Voice quality",1,2); self.a_reco=self.label("Run analysis to receive recommended RVC settings.","analyze"); self.a_reco.setWordWrap(True); ax.addWidget(self.a_reco,2,0,1,4); av.addWidget(self.analysis_box); self.cl.addWidget(analyze)

        conv=self.card("CONVERSION"); cv=conv.layout(); sr=QHBoxLayout(); self.status=self.label("Ready","muted"); sr.addWidget(self.status); sr.addStretch(); self.percent=self.label("0%","value"); sr.addWidget(self.percent); cv.addLayout(sr); self.progress=QProgressBar(); self.progress.setValue(0); cv.addWidget(self.progress); br=QHBoxLayout(); self.convert_btn=QPushButton("✦  CONVERT AUDIO"); self.convert_btn.setObjectName("primary"); self.convert_btn.clicked.connect(self.convert); br.addWidget(self.convert_btn,2); ob=QPushButton("Open Output"); ob.clicked.connect(self.open_output); br.addWidget(ob,1); cv.addLayout(br); self.cl.addWidget(conv); self.cl.addWidget(self.label("RVC stays local on this PC. Output is saved in DJAR_RVC_Output beside the source file.","muted"))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        narrow = self.width() < 1000
        if narrow != self.single_column:
            self.single_column = narrow
            self.grid.removeWidget(self.left); self.grid.removeWidget(self.right)
            if narrow:
                self.grid.addWidget(self.left,0,0,1,1); self.grid.addWidget(self.right,1,0,1,1)
            else:
                self.grid.addWidget(self.left,0,0); self.grid.addWidget(self.right,0,1)

    def card(self,title):
        f=QFrame(); f.setObjectName("card"); l=QVBoxLayout(f); l.setContentsMargins(18,16,18,18); l.setSpacing(8); l.addWidget(self.label(title,"section")); return f
    def slider(self,layout,label,lo,hi,value,suffix):
        box=QVBoxLayout(); h=QHBoxLayout(); h.addWidget(QLabel(label)); h.addStretch(); v=self.label(f"{value}{suffix}","value"); h.addWidget(v); box.addLayout(h); s=QSlider(Qt.Horizontal); s.setRange(lo,hi); s.setValue(value); s.valueChanged.connect(lambda n,out=v,suf=suffix: out.setText(f"{n}{suf}")); box.addWidget(s); layout.addLayout(box); return s
    def analysis_value(self,layout,name,row,col):
        box=QVBoxLayout(); box.addWidget(self.label(name,"muted")); val=self.label("—","value"); box.addWidget(val); layout.addLayout(box,row,col); return val
    def set_badge(self,text,obj):
        self.badge.setText(text); self.badge.setObjectName(obj); self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge); self.badge.update()
    def restore(self):
        self.api.setText(self.saved.get("api",DEFAULT_API)); self.f0.setCurrentIndex(self.saved.get("f0",0))
        for w,k,d in [(self.pitch,"pitch",0),(self.index_rate,"index_rate",75),(self.protect,"protect",33),(self.filter_radius,"filter",3),(self.resample,"resample",0),(self.rms,"rms",25)]:
            val=self.saved.get(k,d)
            if k=="resample" and (not isinstance(val,(int,float)) or val < 1000): val=0
            w.setValue(int(val))

    def save(self):
        save_settings({"api":self.api.text().strip(),"f0":self.f0.currentIndex(),"pitch":self.pitch.value(),"index_rate":self.index_rate.value(),"protect":self.protect.value(),"filter":self.filter_radius.value(),"resample":self.resample.value(),"rms":self.rms.value()})
    def api_url(self,path=""): return self.api.text().strip().rstrip("/")+path

    def test_connection(self):
        base=self.api.text().strip().rstrip("/")
        if not base: return
        self.set_badge("●  RVC CHECKING…","checking"); self.status.setText("Checking RVC server…"); self.test_btn.setEnabled(False)
        def fn(p):
            from urllib.parse import urlparse
            u=urlparse(base); host=u.hostname or "127.0.0.1"; port=u.port or (443 if u.scheme=="https" else 80)
            try:
                with socket.create_connection((host,port),timeout=2): pass
            except Exception as e:
                raise RuntimeError(f"RVC is not reachable at {host}:{port}.\n\n{e}")
            return {"host":host,"port":port}
        def done(info):
            self.test_btn.setEnabled(True); self.set_badge("●  RVC CONNECTED","online"); self.status.setText(f"RVC connected · {info['host']}:{info['port']}")
        self.run(fn,done)

    def discover_voice_choices(self):
        base=self.api.text().strip().rstrip("/")
        choices=[]
        try:
            r=requests.get(base+"/config",timeout=5)
            if r.ok:
                obj=r.json()
                def walk(v):
                    if isinstance(v,dict):
                        for key,val in v.items():
                            if key in ("choices","value","label") and isinstance(val,list):
                                for item in val:
                                    if isinstance(item,str) and item.lower().endswith(".pth"):
                                        choices.append(item)
                            walk(val)
                    elif isinstance(v,list):
                        for item in v: walk(item)
                    elif isinstance(v,str) and v.lower().endswith(".pth"):
                        choices.append(v)
                walk(obj)
        except Exception:
            pass
        if not choices:
            r=requests.post(base+"/run/infer_refresh",json={"data":[]},timeout=20); r.raise_for_status()
            data=r.json().get("data",[])
            if isinstance(data,list) and data:
                first=data[0]
                if isinstance(first,str) and first.lower().endswith(".pth"):
                    choices.append(first)
        return list(dict.fromkeys(choices))

    def refresh_voices(self):
        self.refresh_btn.setEnabled(False); self.status.setText("Refreshing voice models…")
        def fn(p):
            p.emit(20,"Reading RVC model list…")
            vals=self.discover_voice_choices()
            p.emit(100,"Voice list refreshed")
            return vals
        def done(vals):
            self.refresh_btn.setEnabled(True); current=self.voice.currentText(); self.voice.blockSignals(True); self.voice.clear()
            if vals:
                for name in vals: self.voice.addItem(name,name)
                idx=self.voice.findText(current)
                self.voice.setCurrentIndex(idx if idx>=0 else 0)
            else:
                self.voice.addItem("No voice models detected","")
            self.voice.blockSignals(False)
            self.status.setText(f"Voice list refreshed · {len(vals)} model(s)")
        self.run(fn,done,True)

    def voice_changed(self,index):
        model=self.voice.itemData(index)
        if not model or not str(model).lower().endswith(".pth"):
            return
        self.active_voice=str(model)

    def activate_voice(self, model, progress=None):
        if progress: progress.emit(20,"Loading selected RVC voice…")
        protect=self.protect.value()/100.0
        r=requests.post(self.api_url("/run/infer_change_voice"),json={"data":[model,protect,protect]},timeout=180)
        r.raise_for_status()
        obj=r.json(); data=obj.get("data",[])
        if not isinstance(data,list) or len(data)<1:
            raise RuntimeError("RVC did not return the speaker ID after loading the selected model.")
        try:
            spk=int(float(data[0]))
        except Exception:
            raise RuntimeError(f"RVC returned an invalid speaker ID: {data[0]}")
        self.active_spk=spk
        if len(data)>3 and isinstance(data[3],str) and data[3]: self.active_index=data[3]
        if len(data)>4 and isinstance(data[4],str) and data[4]: self.active_index=data[4]
        if progress: progress.emit(32,"RVC voice loaded")
        return spk

    def pick_audio(self):
        path,_=QFileDialog.getOpenFileName(self,"Select audio","","Audio files (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*.*)")
        if path:
            self.audio_path.setText(path); self.audio_name.setText("🎵  "+Path(path).name); self.analysis_status.setText("Local audio selected · ready to analyze")
            self.a_pitch.setText("—"); self.a_duration.setText("—"); self.a_sr.setText("—"); self.a_quality.setText("—"); self.a_reco.setText("Run analysis to receive recommended RVC settings.")

    def pick_index(self):
        path,_=QFileDialog.getOpenFileName(self,"Select feature index","","Index files (*.index);;All files (*.*)")
        if path: self.index_path.setText(path)

    def analyze(self):
        audio=self.audio_path.text().strip()
        if not audio or not os.path.isfile(audio):
            QMessageBox.warning(self,"Input required","Please select a valid audio file first.")
            return
        self.analyze_btn.setEnabled(False); self.analysis_status.setText("Analyzing locally…"); self.status.setText("Analyzing vocal locally…")
        def fn(p): return analyze_audio(audio,p)
        def done(r):
            self.analyze_btn.setEnabled(True)
            self.a_pitch.setText(f"{r['median_f0']:.0f} Hz" if r['median_f0'] else "Not detected")
            self.a_duration.setText(f"{r['duration']:.1f} s"); self.a_sr.setText(f"{r['sample_rate']} Hz"); self.a_quality.setText(r['quality'])
            self.pitch.setValue(0); self.f0.setCurrentText("RMVPE"); self.index_rate.setValue(r['index_rate']); self.protect.setValue(r['protect']); self.filter_radius.setValue(r['median_filter']); self.resample.setValue(0); self.rms.setValue(r['rms_mix'])
            self.a_reco.setText(f"Applied: RMVPE · Index {r['index_rate']}% · Protect {r['protect']}% · Median {r['median_filter']} · Volume {r['rms_mix']}% · Resample Original · Transpose 0. These are starting values; the target model can still require manual tuning.")
            self.analysis_status.setText("✓ Local analysis complete · audio was not uploaded"); self.status.setText("✓ Vocal analyzed · settings optimized"); self.save()
        self.run(fn,done,True)

    def convert(self):
        audio=self.audio_path.text().strip()
        if not audio or not os.path.isfile(audio):
            QMessageBox.warning(self,"Input required","Please select a valid audio file first.")
            return
        model=self.voice.currentData() or self.active_voice
        if not model or not str(model).lower().endswith(".pth"):
            QMessageBox.warning(self,"Voice model required","Select a valid .pth voice model first, then try again.")
            return
        self.save(); self.set_busy(True); self.update_progress(5,"Preparing conversion…")
        pitch=self.pitch.value(); index_rate=self.index_rate.value(); protect=self.protect.value(); filt=self.filter_radius.value(); resample=self.resample.value(); rms=self.rms.value(); f0=self.f0.currentText().lower(); manual_idx=self.index_path.text().strip()
        def fn(progress):
            spk=self.activate_voice(str(model),progress)
            idx=manual_idx or self.active_index or ""
            progress.emit(40,"Sending audio to RVC…")
            empty={"name":"","data":""}
            payload={"data":[spk,audio,pitch,empty,f0,idx,"",index_rate/100.0,filt,resample,rms/100.0,protect/100.0]}
            progress.emit(45,"RVC is processing the conversion…")
            r=requests.post(self.api_url("/run/infer_convert"),json=payload,timeout=3600)
            r.raise_for_status()
            obj=r.json(); data=obj.get("data",[]); ao=data[1] if isinstance(data,list) and len(data)>1 else None
            if not isinstance(ao,dict) or "data" not in ao:
                info=data[0] if isinstance(data,list) and data else ""
                raise RuntimeError("RVC returned no converted audio.\n\n"+str(info))
            encoded=str(ao["data"])
            raw=encoded.split(",",1)[-1]
            try:
                decoded=base64.b64decode(raw)
            except Exception as exc:
                raise RuntimeError(f"Could not decode RVC output audio: {exc}")
            out_dir=Path(audio).parent/"DJAR_RVC_Output"; out_dir.mkdir(exist_ok=True); out=out_dir/(Path(audio).stem+"_RVC.wav"); out.write_bytes(decoded)
            progress.emit(100,"Conversion complete")
            return str(out)
        self.run(fn,self.convert_done,True)

    def convert_done(self,out):
        self.set_busy(False); self.last_output=out; self.update_progress(100,"✓ Conversion complete"); QMessageBox.information(self,"Conversion complete","Your converted audio is ready.\n\n"+out)
    def update_progress(self,v,msg): self.progress.setValue(int(v)); self.percent.setText(f"{int(v)}%"); self.status.setText(msg)
    def failed(self,msg): self.set_busy(False); self.test_btn.setEnabled(True); self.progress.setValue(0); self.percent.setText("0%"); self.status.setText("✕ Operation failed"); QMessageBox.critical(self,"RVC Error",msg)
    def set_busy(self,b): self.convert_btn.setEnabled(not b); self.refresh_btn.setEnabled(not b); self.analyze_btn.setEnabled(not b)
    def run(self,fn,done,progress=False):
        self.thread=QThread(self); worker=Worker(fn); worker.moveToThread(self.thread); self.thread.started.connect(worker.run)
        worker.finished.connect(done); worker.failed.connect(self.failed)
        if progress: worker.progress.connect(self.update_progress)
        worker.finished.connect(self.thread.quit); worker.failed.connect(self.thread.quit); worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()
    def open_output(self):
        audio=self.audio_path.text().strip(); target=Path(self.last_output if self.last_output else (Path(audio).parent/"DJAR_RVC_Output" if audio else ""))
        if not str(target): return
        if target.is_file(): target=target.parent
        target.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
    def closeEvent(self,event): self.save(); event.accept()


if __name__ == "__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_TITLE); app.setFont(QFont("Segoe UI",10)); w=App(); w.show(); sys.exit(app.exec())
