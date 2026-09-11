import socket
from urllib.parse import urlparse

from PySide6.QtWidgets import QApplication, QMessageBox

import studio_v2


def test_connection(self):
    api = self.api.text().strip().rstrip("/")
    if not api:
        QMessageBox.warning(self, "RVC API", "Enter the RVC API address first.")
        return
    parsed = urlparse(api)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    self.test_btn.setEnabled(False)
    self.set_badge("●  RVC CHECKING...", "checking")
    self.status.setText(f"Checking {host}:{port} ...")
    QApplication.processEvents()
    try:
        with socket.create_connection((host, port), timeout=1.0):
            pass
    except OSError as exc:
        self.test_btn.setEnabled(True)
        self.set_badge("●  RVC OFFLINE", "offline")
        self.status.setText(f"RVC offline · {host}:{port}")
        QMessageBox.critical(self, "RVC Connection Failed", f"RVC is not reachable at:\n{api}\n\n{exc}")
        return
    self.test_btn.setEnabled(True)
    self.set_badge("●  RVC CONNECTED", "online")
    self.status.setText(f"RVC connected · TCP {host}:{port}")


def _extract_choices(obj):
    found = []
    if isinstance(obj, dict):
        label = str(obj.get("label", "")).lower()
        props = obj.get("props") if isinstance(obj.get("props"), dict) else {}
        choices = props.get("choices")
        if choices is None:
            choices = obj.get("choices")
        if isinstance(choices, list):
            if ("voice" in label or "infer" in label or "speaker" in label) or len(choices) > 1:
                for item in choices:
                    value = item[0] if isinstance(item, (list, tuple)) and item else item
                    if isinstance(value, str) and value.strip():
                        found.append(value.strip())
        for value in obj.values():
            found.extend(_extract_choices(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_extract_choices(value))
    return found


def refresh_voices(self):
    """Discover actual RVC voice choices from Gradio config, with API fallback.

    The documented /run/infer_refresh endpoint returns the currently selected
    voice, not the complete dropdown choices. The old code incorrectly expected
    that response to be a list, so it always fell back to Speaker ID 0.
    """
    base = self.api.text().strip().rstrip("/")
    if not base:
        return
    self.refresh_btn.setEnabled(False)
    self.status.setText("Discovering RVC voice models...")
    QApplication.processEvents()

    choices = []
    try:
        r = studio_v2.requests.get(base + "/config", timeout=5)
        r.raise_for_status()
        choices = _extract_choices(r.json())
    except Exception:
        choices = []

    # Deduplicate while preserving order and prefer meaningful model names.
    unique = []
    seen = set()
    for item in choices:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if not unique:
        try:
            r = studio_v2.requests.post(base + "/run/infer_refresh", json={"data": []}, timeout=10)
            r.raise_for_status()
            data = r.json().get("data", [])
            if isinstance(data, list) and data and isinstance(data[0], str) and data[0].strip():
                unique = [data[0].strip()]
        except Exception:
            pass

    self.voice.clear()
    if unique:
        for i, name in enumerate(unique):
            self.voice.addItem(name, str(i))
        self.status.setText(f"Voice models loaded · {len(unique)} model(s)")
    else:
        self.voice.addItem("No voice models detected", "0")
        self.status.setText("No voice models found · check RVC weights/models folder")
    self.refresh_btn.setEnabled(True)


studio_v2.App.test_connection = test_connection
studio_v2.App.refresh_voices = refresh_voices

_original_init = studio_v2.App.__init__


def init(self):
    # Suppress the legacy automatic startup timer while constructing the window.
    original_single_shot = studio_v2.QTimer.singleShot
    studio_v2.QTimer.singleShot = staticmethod(lambda *args, **kwargs: None)
    try:
        _original_init(self)
    finally:
        studio_v2.QTimer.singleShot = original_single_shot
    self.test_btn.setEnabled(True)
    self.set_badge("●  RVC OFFLINE", "offline")
    self.status.setText("Ready · click Test Connection")


studio_v2.App.__init__ = init


if __name__ == "__main__":
    app = QApplication([])
    app.setApplicationName(studio_v2.APP_TITLE)
    window = studio_v2.App()
    window.show()
    app.exec()
