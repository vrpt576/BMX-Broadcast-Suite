"""Windows notification-area controller for BMX Broadcast Suite."""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
import ctypes
from pathlib import Path

from PIL import Image
import pystray

from connector.service_status import ServiceStatus, read_status, status_lines, windows_service_state

SERVICE_NAME = "BMXBroadcastSuite"
ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "data" / "bbs-icon.png"
ICON_FALLBACK = ROOT / "assets" / "bbs-icon.png"
BASE_URL = os.environ.get("BBS_TRAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class BBSWindowsTray:
    def __init__(self) -> None:
        self.running = True
        self.busy = False
        self.status = ServiceStatus(
            service="starting",
            api="unavailable",
            database="unknown",
        )
        self.icon = pystray.Icon(
            "bbs-tray",
            self._load_icon(),
            "BMX Broadcast Suite — Checking status",
            menu=self._menu(),
        )

    @staticmethod
    def _load_icon() -> Image.Image:
        path = ICON if ICON.is_file() else ICON_FALLBACK
        with Image.open(path) as image:
            return image.convert("RGBA")

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda _item: (
                    f"BMX Broadcast Suite {self.status.version or '1.3.0'}"
                ),
                None,
                enabled=False,
            ),
            pystray.MenuItem(
                lambda _item: "\n".join(status_lines(self.status)),
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Open Race Director",
                lambda _icon, _item: self._open("/director"),
                default=True,
            ),
            pystray.MenuItem(
                "Open Setup",
                lambda _icon, _item: self._open("/setup"),
            ),
            pystray.MenuItem(
                "Open Configuration",
                lambda _icon, _item: self._open("/configuration"),
            ),
            pystray.MenuItem(
                "Open Theme Manager",
                lambda _icon, _item: self._open("/themes"),
            ),
            pystray.MenuItem(
                "Open Diagnostics",
                lambda _icon, _item: self._open("/diagnostics"),
            ),
            pystray.MenuItem(
                "Open Logs",
                lambda _icon, _item: self._open("/logs"),
            ),
            pystray.MenuItem(
                "Open Lineup Preview",
                lambda _icon, _item: self._open("/overlay/lineup?preview=true"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start BBS",
                lambda _icon, _item: self._run_in_background(lambda: self._service_action("start")),
                enabled=lambda _item: not self.busy and self.status.service not in ("running", "starting"),
            ),
            pystray.MenuItem(
                "Stop BBS",
                lambda _icon, _item: self._run_in_background(lambda: self._service_action("stop")),
                enabled=lambda _item: not self.busy and self.status.service in ("running", "stopping"),
            ),
            pystray.MenuItem(
                "Restart BBS",
                lambda _icon, _item: self._run_in_background(self._restart),
                enabled=lambda _item: not self.busy and self.status.service == "running",
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit Tray Icon",
                lambda _icon, _item: self._quit(),
            ),
        )

    def _open(self, page: str) -> None:
        webbrowser.open(f"{BASE_URL}{page}")

    def _notify(self, message: str) -> None:
        try:
            self.icon.notify(message, "BMX Broadcast Suite")
        except NotImplementedError:
            # Balloon notifications aren't available on every backend; the
            # tray tooltip/status lines still reflect the real state.
            pass

    def _run_in_background(self, action) -> None:
        """Run a service-control action off pystray's callback thread.

        Service start/stop/restart involve a UAC elevation prompt and can
        take several seconds; running them here keeps the tray responsive
        and lets `busy` disable the menu items so a second click can't race
        an action already in flight.
        """
        if self.busy:
            return
        self.busy = True
        self.icon.update_menu()

        def worker() -> None:
            try:
                action()
            finally:
                self.busy = False
                self.icon.update_menu()

        threading.Thread(target=worker, daemon=True).start()

    def _service_action(self, action: str, *, timeout: float = 20.0) -> bool:
        """Elevate and run `sc.exe <action>`, then confirm it actually took effect.

        ShellExecuteW's return code only reports whether Windows could launch
        the elevated process. A value greater than 32 there is *not* proof the
        service changed state — sc.exe can still fail once elevated (a
        dependent service, a hung process, a permissions issue), and if the
        user cancels the UAC prompt, ShellExecuteW returns 1223
        (ERROR_CANCELLED), which the old `result <= 32` check let straight
        through as a false success. The only reliable signal is polling the
        actual service state afterward.
        """
        expected = "running" if action == "start" else "stopped"
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "sc.exe", f'{action} "{SERVICE_NAME}"', None, 0
        )
        if result <= 32:
            self._notify(f"Could not launch the prompt to {action} BBS (Windows error {result}).")
            return False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if windows_service_state(SERVICE_NAME) == expected:
                self.status = read_status(BASE_URL, SERVICE_NAME)
                return True
        self.status = read_status(BASE_URL, SERVICE_NAME)
        self._notify(
            f"BBS did not reach the '{expected}' state after {action}. "
            "The elevation prompt may have been cancelled or dismissed, or the "
            "service is stuck — check services.msc."
        )
        return False

    def _restart(self) -> None:
        if not self._service_action("stop"):
            self._notify("Restart stopped: BBS did not stop cleanly.")
            return
        if not self._service_action("start"):
            self._notify("Restart failed: BBS stopped but did not start back up.")

    def _quit(self) -> None:
        self.running = False
        self.icon.stop()

    def _refresh_loop(self) -> None:
        while self.running:
            self.status = read_status(BASE_URL, SERVICE_NAME)
            lines = status_lines(self.status)
            self.icon.title = "BMX Broadcast Suite\n" + "\n".join(lines)
            self.icon.update_menu()
            time.sleep(5)

    def run(self) -> None:
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        self.icon.run()


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("The Windows tray controller only runs on Windows.")
    BBSWindowsTray().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
