"""Config-aware BBS launcher with persistent early-startup diagnostics."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import traceback


def _startup_error_file() -> Path:
    try:
        from connector.config import runtime_root

        return runtime_root() / "startup-error.log"
    except Exception:
        return Path(os.environ.get("TEMP", tempfile.gettempdir())) / "bbs-startup-error.log"


def main() -> int:
    startup_error = _startup_error_file()
    try:
        startup_error.unlink(missing_ok=True)
        import uvicorn

        from connector.config import get_settings

        settings = get_settings()
        uvicorn.run(
            "connector.main:app",
            host=settings.app_host,
            port=settings.app_port,
            log_level=settings.log_level.lower(),
        )
        return 0
    except BaseException:
        try:
            startup_error.parent.mkdir(parents=True, exist_ok=True)
            startup_error.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
