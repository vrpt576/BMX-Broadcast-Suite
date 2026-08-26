#!/usr/bin/env python3
"""Save a Sqorz internet-API event payload to a file for offline replay.

Carry a real event with you: capture it while you have internet, then point
BBS at the saved file with BBS_SQORZ_MODE=file / BBS_SQORZ_FILE_PATH -- see
docs/sqorz-on-site-runbook.md. The file is exactly what
connector/services/sqorz_service.py's internet mode fetches, just saved to
disk, so it replays through the identical parsing/matching/overlay pipeline.

Stdlib only. No dependency on the rest of this repo.

Usage:
    python scripts/sqorz_capture.py --event-id 6a8198e2d91badc23cb0c54f --out demo-event.json

Find an event id from https://our.sqorz.com/json/org/<orgCode>
(e.g. usabmx) -- look for an event with a recent eventDate in its "events"
list and use its eventId.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 10.0


def fetch(event_id: str, timeout: float) -> dict:
    url = f"https://our.sqorz.com/json/event/{event_id}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "BBS-Sqorz-Capture/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event-id", required=True, help="Sqorz eventId, e.g. 6a8198e2d91badc23cb0c54f")
    parser.add_argument("--out", required=True, help="Where to save the payload, e.g. demo-event.json")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default {DEFAULT_TIMEOUT}).")
    args = parser.parse_args()

    print(f"Fetching https://our.sqorz.com/json/event/{args.event_id} ...")
    try:
        payload = fetch(args.event_id, args.timeout)
    except HTTPError as exc:
        print(f"FAILED: HTTP {exc.code} -- {exc.reason}")
        return 1
    except (URLError, TimeoutError, OSError) as exc:
        print(f"FAILED: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAILED: response wasn't valid JSON -- {exc}")
        return 1

    class_count = len(payload.get("classRanks") or [])
    if class_count == 0:
        print("WARNING: response has no classRanks -- wrong event id, or the event hasn't started scoring yet.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved {class_count} class(es) to {out_path.resolve()}")
    print()
    print("To replay it, set in BBS's config:")
    print("  BBS_SQORZ_ENABLED=true")
    print("  BBS_SQORZ_MODE=file")
    print(f"  BBS_SQORZ_FILE_PATH={out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
