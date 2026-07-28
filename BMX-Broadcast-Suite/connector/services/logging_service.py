"""Central logging configuration and recent-log access for BBS."""
from __future__ import annotations

import logging
from collections import deque
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from threading import RLock

_RECENT: deque[dict[str, str]] = deque(maxlen=1000)
_LOCK = RLock()


class RecentLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            item = {
                "timestamp": self.formatter.formatTime(record, "%Y-%m-%d %H:%M:%S") if self.formatter else "",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            with _LOCK:
                _RECENT.append(item)
        except Exception:
            self.handleError(record)


def configure_logging(level: str, log_dir: Path, retention_days: int = 14) -> Path:
    """Configure console, daily rotating file, and in-memory recent logging."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bbs.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=max(1, retention_days), encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    recent = RecentLogHandler()
    recent.setFormatter(formatter)
    root.addHandler(recent)
    return log_file


def recent_logs(level: str | None = None, search: str = "", limit: int = 200) -> list[dict[str, str]]:
    with _LOCK:
        items = list(_RECENT)
    if level:
        items = [item for item in items if item["level"] == level.upper()]
    if search:
        needle = search.lower()
        items = [item for item in items if needle in item["message"].lower() or needle in item["logger"].lower()]
    return items[-max(1, min(limit, 1000)):]
