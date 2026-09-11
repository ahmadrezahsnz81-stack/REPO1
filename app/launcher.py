import socket

from PySide6.QtWidgets import QApplication, QMessageBox

import studio_v2


def test_connection(self):
    api = self.api.text().strip().rstrip("/")
    if not api:
        QMessageBox.warning(self, "RVC API", "Enter the RVC API address first.")
        return

    from urllib.parse import urlparse
    parsed = urlparse(api)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    self.test_btn.setEnabled(False)
    self.set_badge("●  RVC CHECKING...", "checking")
    self.status.setText(f"Checking {host}:{port} ...")

    def fn(progress):
        with socket.create_connection((host, port), timeout=1.5):
            pass
        try:
            r = studio_v2.requests.get(api, timeout=2, allow_redirects=True)
            return r.status_code
        except Exception:
            return None

    def done(code):
        self.test_btn.setEnabled(True)
        self.set_badge("●  RVC CONNECTED", "online")
        if code is None:
            self.status.setText(f"RVC service reachable · TCP {port} · HTTP check skipped")
        else:
            self.status.setText(f"RVC service reachable · TCP {port} · HTTP {code}")

    def failed(message):
        self.test_btn.setEnabled(True)
        self.set_badge("●  RVC OFFLINE", "offline")
        self.status.setText("RVC connection failed")
        QMessageBox.critical(self, "RVC Connection Failed", f"Could not reach RVC at:\n{api}\n\n{message}")

    self.run(fn, done)


studio_v2.App.test_connection = test_connection

_original_init = studio_v2.App.__init__


def init(self):
    # Suppress the old startup timer so connection testing is manual only.
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
