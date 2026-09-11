import socket
from urllib.parse import urlparse

from PySide6.QtWidgets import QApplication, QMessageBox

import studio_v2


def test_connection(self):
    """Fast, deterministic local TCP health check.

    We intentionally do not use the RVC action endpoints or an HTTP request here.
    The only question for this button is: is something listening on the configured
    host/port? This avoids the previous worker/HTTP hang entirely.
    """
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
        # Direct TCP check. Localhost should return almost immediately.
        with socket.create_connection((host, port), timeout=1.0):
            pass
    except OSError as exc:
        self.test_btn.setEnabled(True)
        self.set_badge("●  RVC OFFLINE", "offline")
        self.status.setText(f"RVC offline · {host}:{port}")
        QMessageBox.critical(
            self,
            "RVC Connection Failed",
            f"RVC is not reachable at:\n{api}\n\n"
            f"{exc}\n\n"
            f"Make sure the RVC WebUI/API is running on port {port}."
        )
        return

    self.test_btn.setEnabled(True)
    self.set_badge("●  RVC CONNECTED", "online")
    self.status.setText(f"RVC connected · TCP {host}:{port}")


studio_v2.App.test_connection = test_connection

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
