import socket

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import studio_v2


_ORIGINAL_TEST_CONNECTION = studio_v2.App.test_connection


def test_connection(self):
    # The old build scheduled an automatic connection test during startup.
    # That made the Test Connection button look disabled while the startup
    # worker was running. Startup is now passive; testing happens only after
    # the user clicks the button.
    if not getattr(self, "_connection_tests_enabled", True):
        return

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
        # First prove that the TCP service is reachable. This avoids relying
        # on an RVC action endpoint for a health check.
        with socket.create_connection((host, port), timeout=3):
            pass

        try:
            r = studio_v2.requests.get(api, timeout=5, allow_redirects=True)
            return (True, port, r.status_code)
        except Exception as exc:
            # A listening RVC service is still a valid local connection even
            # when its WebUI root does not answer like a normal HTTP page.
            return (True, port, None, str(exc))

    def done(result):
        self.test_btn.setEnabled(True)
        if len(result) == 3:
            _, checked_port, code = result
            self.set_badge("●  RVC CONNECTED", "online")
            self.status.setText(f"RVC service reachable · TCP {checked_port} · HTTP {code}")
        else:
            _, checked_port, _, detail = result
            self.set_badge("●  RVC CONNECTED", "online")
            self.status.setText(f"RVC service reachable · TCP {checked_port} · HTTP check skipped")

    def failed(message):
        self.test_btn.setEnabled(True)
        self.set_badge("●  RVC OFFLINE", "offline")
        self.status.setText("RVC connection failed")
        QMessageBox.critical(self, "RVC Connection Failed", f"Could not reach RVC at:\n{api}\n\n{message}")

    self.run(fn, done)


studio_v2.App.test_connection = test_connection


_original_init = studio_v2.App.__init__


def init(self):
    self._connection_tests_enabled = False
    _original_init(self)
    # The patched test method makes the scheduled startup probe a no-op.
    # Enable manual testing only after the window is fully initialized.
    self._connection_tests_enabled = True
    self.test_btn.setEnabled(True)
    self.set_badge("●  RVC OFFLINE", "offline")
    self.status.setText("Ready · click Test Connection")
    QTimer.singleShot(0, lambda: self.test_btn.setEnabled(True))


studio_v2.App.__init__ = init


if __name__ == "__main__":
    app = QApplication([])
    app.setApplicationName(studio_v2.APP_TITLE)
    window = studio_v2.App()
    window.show()
    app.exec()
