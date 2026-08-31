"""Ubuntu/Linux system tray controller for the BBS machine service."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

try:
    import gi

    gi.require_version("Gtk", "3.0")
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ValueError, ImportError):
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3
    from gi.repository import GLib, Gtk
except (ImportError, ValueError) as exc:  # pragma: no cover - depends on desktop packages
    raise SystemExit(
        "BBS tray dependencies are missing. Install python3-gi and "
        "gir1.2-ayatanaappindicator3-0.1."
    ) from exc

from connector.service_status import read_status, status_lines

UNIT = "bbs-connector.service"
ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "logo.png"
BASE_URL = os.environ.get("BBS_TRAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class BBSTray:
    def __init__(self) -> None:
        self.indicator = AppIndicator3.Indicator.new(
            "bbs-tray",
            str(ICON),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_icon_full(str(ICON), "BMX Broadcast Suite")
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("BMX Broadcast Suite")

        self.menu = Gtk.Menu()
        self.header = self._item("BMX Broadcast Suite 1.3.1", sensitive=False)
        self.status_items = [self._item("Checking status…", sensitive=False) for _ in range(3)]
        self.menu.append(Gtk.SeparatorMenuItem())

        for label, url in (
            ("Open Setup", "/setup"),
            ("Open Manual", "/manual"),
            ("Open Controller", "/controller"),
            ("Open Configuration", "/configuration"),
            ("Open Diagnostics", "/diagnostics"),
            ("Open Logs", "/logs"),
            ("Open Lineup Preview", "/overlay/lineup?preview=true"),
        ):
            self._item(label, lambda _item, page=url: webbrowser.open(f"{BASE_URL}{page}"))

        self.menu.append(Gtk.SeparatorMenuItem())
        self.start_item = self._item("Start Service", lambda _item: self._service_action("start"))
        self.stop_item = self._item("Stop Service", lambda _item: self._service_action("stop"))
        self.restart_item = self._item("Restart Service", lambda _item: self._service_action("restart"))
        self._item("View Service Log", lambda _item: self._open_terminal_log())
        self.menu.append(Gtk.SeparatorMenuItem())
        self._item("Exit Tray Icon", lambda _item: Gtk.main_quit())

        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self._refresh()
        GLib.timeout_add_seconds(5, self._refresh)

    def _item(self, label: str, callback=None, *, sensitive: bool = True):
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(sensitive)
        if callback:
            item.connect("activate", callback)
        self.menu.append(item)
        return item

    def _service_action(self, action: str) -> None:
        # pkexec provides an explicit desktop authentication prompt for machine-service changes.
        subprocess.Popen(["pkexec", "systemctl", action, UNIT])
        GLib.timeout_add_seconds(2, self._refresh)

    def _open_terminal_log(self) -> None:
        commands = [
            ["kgx", "--", "journalctl", "-u", UNIT, "-f"],
            ["gnome-terminal", "--", "journalctl", "-u", UNIT, "-f"],
            ["x-terminal-emulator", "-e", "journalctl", "-u", UNIT, "-f"],
        ]
        for command in commands:
            try:
                subprocess.Popen(command)
                return
            except FileNotFoundError:
                continue
        webbrowser.open(f"{BASE_URL}/logs")

    def _refresh(self) -> bool:
        status = read_status(BASE_URL, UNIT)
        lines = status_lines(status)
        while len(lines) < len(self.status_items):
            lines.append("")
        for item, text in zip(self.status_items, lines):
            item.set_label(text)
            item.set_visible(bool(text))

        running = status.service == "running"
        self.start_item.set_sensitive(not running)
        self.stop_item.set_sensitive(running)
        self.restart_item.set_sensitive(running)
        self.header.set_label(f"BMX Broadcast Suite {status.version or '1.3.1'}")
        return True


def main() -> int:
    BBSTray()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
