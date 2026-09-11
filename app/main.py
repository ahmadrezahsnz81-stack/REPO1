import base64
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import requests
except ImportError:
    requests = None

APP_TITLE = "DJAR RVC Studio"
DEFAULT_API = "http://127.0.0.1:7897"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x680")
        self.minsize(880, 620)
        self.configure(bg="#101217")
        self.api = tk.StringVar(value=DEFAULT_API)
        self.audio = tk.StringVar()
        self.voice = tk.StringVar(value="0")
        self.f0 = tk.StringVar(value="rmvpe")
        self.index = tk.StringVar()
        self.pitch = tk.IntVar(value=0)
        self.index_rate = tk.DoubleVar(value=0.75)
        self.filter_radius = tk.IntVar(value=3)
        self.resample = tk.IntVar(value=0)
        self.rms = tk.DoubleVar(value=0.25)
        self.protect = tk.DoubleVar(value=0.33)
        self.status = tk.StringVar(value="Ready")
        self.progress = tk.DoubleVar(value=0)
        self._styles()
        self._ui()

    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background="#101217", foreground="#e8ebf2", font=("Segoe UI", 10))
        s.configure("TFrame", background="#101217")
        s.configure("Card.TFrame", background="#181c24")
        s.configure("TLabel", background="#101217", foreground="#e8ebf2")
        s.configure("Card.TLabel", background="#181c24", foreground="#e8ebf2")
        s.configure("Title.TLabel", background="#101217", foreground="#ffffff", font=("Segoe UI Semibold", 24))
        s.configure("Muted.TLabel", background="#101217", foreground="#9299a8", font=("Segoe UI", 9))
        s.configure("CardMuted.TLabel", background="#181c24", foreground="#9299a8", font=("Segoe UI", 9))
        s.configure("Accent.TButton", padding=11, font=("Segoe UI Semibold", 11))
        s.configure("TButton", padding=8)
        s.configure("TEntry", padding=8)
        s.configure("TCombobox", padding=7)
        s.configure("Horizontal.TProgressbar", thickness=8)

    def _ui(self):
        head = ttk.Frame(self, padding=(28, 22))
        head.pack(fill="x")
        ttk.Label(head, text="DJAR RVC Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text="Portable Windows controller for your local RVC API", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

        api = ttk.Frame(head)
        api.pack(fill="x", pady=(16, 0))
        ttk.Label(api, text="RVC API").pack(side="left")
        ttk.Entry(api, textvariable=self.api, width=44).pack(side="left", padx=10)
        ttk.Button(api, text="Test Connection", command=self.test).pack(side="left")

        body = ttk.Frame(self, padding=(28, 2))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        left = ttk.Frame(body, style="Card.TFrame", padding=20)
        right = ttk.Frame(body, style="Card.TFrame", padding=20)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Label(left, text="CONVERT", style="Card.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 14))
        ttk.Label(left, text="Voice / Speaker ID", style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(left, style="Card.TFrame")
        row.pack(fill="x", pady=(5, 14))
        ttk.Combobox(row, textvariable=self.voice, values=["0", "1", "2", "3"], width=12).pack(side="left")
        ttk.Button(row, text="Refresh", command=self.refresh).pack(side="left", padx=8)

        ttk.Label(left, text="Input Audio", style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(left, style="Card.TFrame")
        row.pack(fill="x", pady=(5, 18))
        ttk.Entry(row, textvariable=self.audio).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=self.pick_audio).pack(side="left", padx=(8, 0))

        ttk.Label(left, text="F0 Method", style="Card.TLabel").pack(anchor="w")
        ttk.Combobox(left, textvariable=self.f0, values=["rmvpe", "crepe", "harvest", "pm"], state="readonly").pack(fill="x", pady=(5, 18))

        self.slider(left, "Transpose (semitones)", self.pitch, -12, 12)
        self.slider(left, "Index / Feature Ratio", self.index_rate, 0, 1)
        self.slider(left, "Protect Breath / Consonants", self.protect, 0, 0.5)

        ttk.Label(right, text="ADVANCED", style="Card.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 14))
        self.slider(right, "Median Filter Radius", self.filter_radius, 0, 7)
        self.slider(right, "Resample Rate (0 = original)", self.resample, 0, 48000)
        self.slider(right, "Volume Envelope Mix", self.rms, 0, 1)

        ttk.Label(right, text="Feature Index Path", style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(right, style="Card.TFrame")
        row.pack(fill="x", pady=(5, 16))
        ttk.Entry(row, textvariable=self.index).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=self.pick_index).pack(side="left", padx=(8, 0))

        ttk.Separator(right).pack(fill="x", pady=(3, 18))
        ttk.Label(right, text="STATUS", style="Card.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w")
        ttk.Progressbar(right, variable=self.progress, maximum=100).pack(fill="x", pady=(12, 8))
        ttk.Label(right, textvariable=self.status, style="CardMuted.TLabel").pack(anchor="w")
        ttk.Button(right, text="CONVERT AUDIO", style="Accent.TButton", command=self.convert).pack(fill="x", pady=(18, 8))
        ttk.Button(right, text="Open Output Folder", command=self.open_output).pack(fill="x")

        ttk.Label(self, text="RVC must be running locally on 127.0.0.1:7897", style="Muted.TLabel", padding=(28, 8)).pack(fill="x")

    def slider(self, parent, label, variable, lo, hi):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 12))
        top = ttk.Frame(row, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=label, style="Card.TLabel").pack(side="left")
        ttk.Label(top, textvariable=variable, style="Card.TLabel").pack(side="right")
        ttk.Scale(row, from_=lo, to=hi, variable=variable, orient="horizontal").pack(fill="x", pady=(4, 0))

    def pick_audio(self):
        p = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if p: self.audio.set(p)

    def pick_index(self):
        p = filedialog.askopenfilename(filetypes=[("Index", "*.index"), ("All files", "*.*")])
        if p: self.index.set(p)

    def test(self):
        if requests is None:
            self.status.set("Missing requests package")
            return
        self.status.set("Testing RVC...")
        threading.Thread(target=self._test, daemon=True).start()

    def _test(self):
        try:
            r = requests.post(self.api.get() + "/run/infer_clean", json={"data": []}, timeout=15)
            r.raise_for_status()
            self.after(0, lambda: self.status.set("✓ Connected to RVC API"))
        except Exception as e:
            self.after(0, lambda: self.status.set("✕ API unavailable: " + str(e)))

    def refresh(self):
        if requests is None: return
        self.status.set("Refreshing voice list...")
        threading.Thread(target=self._refresh, daemon=True).start()

    def _refresh(self):
        try:
            r = requests.post(self.api.get() + "/run/infer_refresh", json={"data": []}, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", [])
            self.after(0, lambda: self.status.set("Voice list refreshed: " + (str(data[0]) if data else "OK")))
        except Exception as e:
            self.after(0, lambda: self.status.set("Refresh failed: " + str(e)))

    def convert(self):
        if requests is None:
            messagebox.showerror("Dependency", "The portable build is missing its HTTP runtime.")
            return
        if not os.path.isfile(self.audio.get()):
            messagebox.showwarning("Input", "Select a valid audio file first.")
            return
        self.progress.set(5)
        self.status.set("Converting...")
        threading.Thread(target=self._convert, daemon=True).start()

    def _convert(self):
        try:
            empty_f0 = {"name": "none.txt", "data": "data:text/plain;base64," + base64.b64encode(b"").decode()}
            payload = {"data": [
                int(float(self.voice.get() or 0)), self.audio.get(), int(float(self.pitch.get())),
                empty_f0, self.f0.get(), "", self.index.get(), float(self.index_rate.get()),
                int(float(self.filter_radius.get())), int(float(self.resample.get())),
                float(self.rms.get()), float(self.protect.get())
            ]}
            self.after(0, lambda: self.progress.set(20))
            r = requests.post(self.api.get() + "/run/infer_convert", json=payload, timeout=3600)
            r.raise_for_status()
            obj = r.json()
            data = obj.get("data", [])
            audio = data[1] if len(data) > 1 else None
            if not isinstance(audio, dict) or "data" not in audio:
                raise RuntimeError("RVC returned no audio data")
            raw = audio["data"].split(",", 1)[-1]
            out_dir = os.path.join(os.path.dirname(self.audio.get()), "DJAR_RVC_Output")
            os.makedirs(out_dir, exist_ok=True)
            name = os.path.splitext(os.path.basename(self.audio.get()))[0] + "_RVC.wav"
            out = os.path.join(out_dir, name)
            with open(out, "wb") as f: f.write(base64.b64decode(raw))
            self.after(0, lambda: self.done(out))
        except Exception as e:
            self.after(0, lambda: self.fail(str(e)))

    def done(self, out):
        self.progress.set(100)
        self.status.set("✓ Done: " + os.path.basename(out))
        messagebox.showinfo("Complete", "Conversion finished.\n\n" + out)

    def fail(self, msg):
        self.progress.set(0)
        self.status.set("Conversion failed")
        messagebox.showerror("RVC Error", msg)

    def open_output(self):
        if not self.audio.get(): return
        d = os.path.join(os.path.dirname(self.audio.get()), "DJAR_RVC_Output")
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

if __name__ == "__main__":
    App().mainloop()
