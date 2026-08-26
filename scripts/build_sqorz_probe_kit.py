#!/usr/bin/env python3
"""Assemble the emailable Sqorz probe kit: one .zip, three files inside.

Combines scripts/sqorz_probe.py (the canonical, standalone script -- also
usable directly by a developer) with scripts/sqorz_probe_kit/'s launcher and
README into a single flat .zip that can be attached to an email and handed
to someone who has never cloned this repo.

Stdlib only.

Usage:
    python scripts/build_sqorz_probe_kit.py [--out sqorz-probe-kit.zip]
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_SCRIPT = REPO_ROOT / "scripts" / "sqorz_probe.py"
KIT_ASSETS_DIR = REPO_ROOT / "scripts" / "sqorz_probe_kit"


def build(out_path: Path) -> None:
    files = [
        PROBE_SCRIPT,
        KIT_ASSETS_DIR / "Run Sqorz Probe.bat",
        KIT_ASSETS_DIR / "README.txt",
    ]
    missing = [f for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"Missing kit file(s): {', '.join(str(f) for f in missing)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            # Flat inside the zip -- every file at the top level, no
            # subfolder, so "Run Sqorz Probe.bat" finds sqorz_probe.py
            # sitting right next to it once extracted.
            archive.write(file, arcname=file.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "dist" / "sqorz-probe-kit.zip"),
        help="Output .zip path (default: dist/sqorz-probe-kit.zip).",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    build(out_path)
    print(f"Built {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
