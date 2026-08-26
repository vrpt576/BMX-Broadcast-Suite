"""A throwaway mock of Sqorz's LAN scoring API -- GUESSED response shapes.

Sqorz has never published the LAN API's real response format (see
connector/services/sqorz_service.py's module docstring). This reshapes the
real, VERIFIED internet API payload (tests/fixtures/sqorz/hoosier_day3_event.json)
into one plausible guess per function BBS actually calls in LAN mode
(getPhaseBlockSummaries, getPhaseRankDetail), using the same container-key
convention sqorz_service.py's parser already tries first.

What running against this mock proves: BBS forms a correct request (method,
URL, content-type, JSON-array body), handles a 200 response without raising,
falls back correctly when a request times out, and holds last-known-good
data (flagged stale) rather than blanking when the connection drops mid-poll.

What it does NOT prove: that BBS parses Smith Rock's real scoring computer's
actual response shape. That is still unverified until confirmed on site with
scripts/sqorz_probe.py -- do not mistake a pass against this mock for LAN
contract verification. See docs/sqorz-live-timing.md.

Not shipped in the installer (scripts/ is excluded from the MSI payload --
see scripts/build-windows-installer.ps1). stdlib only, no new dependency.

Standalone use:
    python scripts/sqorz_lan_mock.py --port 4343

Then point BBS at it: BBS_SQORZ_MODE=lan, BBS_SQORZ_HOST=127.0.0.1,
BBS_SQORZ_PORT=4343.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sqorz" / "hoosier_day3_event.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _build_phase_block_summaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """GUESS: one "phase block" per distinct phaseCode actually present in a
    class -- Sqorz doesn't publish what a phase block really groups."""
    blocks: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for class_rank in payload.get("classRanks") or []:
        class_code = class_rank.get("classCode")
        class_name = class_rank.get("className")
        phase_codes = {
            detail.get("phaseCode")
            for competitor in class_rank.get("competitorRankSummaries") or []
            for detail in competitor.get("competitorRankDetails") or []
            if detail.get("phaseCode")
        }
        for phase_code in sorted(phase_codes):
            key = (class_code, phase_code)
            if key in seen:
                continue
            seen.add(key)
            blocks.append(
                {"classCode": class_code, "className": class_name, "phaseBlockCode": phase_code}
            )
    return blocks


def _build_phase_rank_detail(
    payload: dict[str, Any], *, class_code: str, phase_block_code: str
) -> list[dict[str, Any]]:
    """GUESS: mirrors the internet API's own per-competitor nested-details
    shape -- one of the two shapes sqorz_service.py's LAN parser already
    tries, and the richer, more internet-API-consistent guess of the two."""
    competitors: list[dict[str, Any]] = []
    for class_rank in payload.get("classRanks") or []:
        if class_rank.get("classCode") != class_code:
            continue
        for competitor in class_rank.get("competitorRankSummaries") or []:
            details = [
                detail
                for detail in competitor.get("competitorRankDetails") or []
                if detail.get("phaseCode") == phase_block_code
            ]
            if not details:
                continue
            competitors.append(
                {
                    "plate": competitor.get("plate"),
                    "firstName": competitor.get("firstName"),
                    "lastName": competitor.get("lastName"),
                    "competitorRankDetails": details,
                }
            )
    return competitors


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: Any) -> None:
        pass  # quiet -- the mock itself is not the thing under test

    def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's own naming
        mock: MockSqorzLanServer = self.server.mock  # type: ignore[attr-defined]
        if mock.delay_seconds:
            time.sleep(mock.delay_seconds)

        parsed = urlparse(self.path)
        if parsed.path != "/api":
            self.send_response(404)
            self.end_headers()
            return
        func = (parse_qs(parsed.query).get("func") or [""])[0]

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"[]"
        try:
            args = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            args = []

        body = mock.respond(func, args)
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class MockSqorzLanServer:
    """See module docstring: GUESSED response shapes, request/response
    mechanics only. Usable as a context manager in tests, or run standalone
    via `python scripts/sqorz_lan_mock.py`."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4343) -> None:
        self.host = host
        self.port = port
        self.payload = _load_fixture()
        self.delay_seconds = 0.0
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def respond(self, func: str, args: list[Any]) -> dict[str, Any]:
        if func == "getPhaseBlockSummaries":
            return {"phaseBlockSummaries": _build_phase_block_summaries(self.payload)}
        if func == "getPhaseRankDetail":
            request = args[0] if args and isinstance(args[0], dict) else {}
            competitors = _build_phase_rank_detail(
                self.payload,
                class_code=request.get("classCode", ""),
                phase_block_code=request.get("phaseBlockCode", ""),
            )
            return {"competitors": competitors}
        return {}

    def start(self) -> None:
        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.mock = self  # type: ignore[attr-defined] -- read back in _Handler
        self.port = self._httpd.server_address[1]  # resolves an ephemeral port:=0
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def __enter__(self) -> "MockSqorzLanServer":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4343)
    args = parser.parse_args()
    print(
        "GUESSED response shapes -- proves BBS's request/response handling, "
        "NOT the real LAN contract. See docs/sqorz-live-timing.md."
    )
    server = MockSqorzLanServer(host=args.host, port=args.port)
    server.start()
    print(f"Mock Sqorz LAN API listening on http://{args.host}:{server.port} -- Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
