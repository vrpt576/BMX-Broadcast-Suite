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

from connector.service_status import ServiceStatus, read_status, status_lines

SERVICE_NAME = "BMXBroadcastSuite"
ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "data" / "bbs-icon.png"
ICON_FALLBACK = ROOT / "assets" / "bbs-icon.png"
BASE_URL = os.environ.get("BBS_TRAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class BBSWindowsTray:
    def __init__(self) -> None:
        self.running = True
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
                    f"BMX Broadcast Suite {self.status.version or '1.2.12'}"
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
                "Open Configuration",
                lambda _icon, _item: self._open("/configuration"),
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
                lambda _icon, _item: self._service_action("start"),
                enabled=lambda _item: self.status.service != "running",
            ),
            pystray.MenuItem(
                "Stop BBS",
                lambda _icon, _item: self._service_action("stop"),
                enabled=lambda _item: self.status.service == "running",
            ),
            pystray.MenuItem(
                "Restart BBS",
                lambda _icon, _item: self._restart(),
                enabled=lambda _item: self.status.service == "running",
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit Tray Icon",
                lambda _icon, _item: self._quit(),
            ),
        )

    def _open(self, page: str) -> None:
        webbrowser.open(f"{BASE_URL}{page}")

    def _service_action(self, action: str) -> None:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "sc.exe", f'{action} "{SERVICE_NAME}"', None, 0
        )
        if result <= 32:
            raise OSError(f"Windows could not {action} the BBS service (ShellExecute {result}).")

    def _restart(self) -> None:
        self._service_action("stop")
        time.sleep(1)
        self._service_action("start")

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
