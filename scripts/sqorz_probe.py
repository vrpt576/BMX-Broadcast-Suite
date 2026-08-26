#!/usr/bin/env python3
"""Sqorz LAN API field probe -- run this on your laptop at the track.

Tells you in under a minute whether the Sqorz LAN scoring API is reachable,
and saves every raw response so the LAN backend
(connector/services/sqorz_service.py) can be finished against the real
shapes -- Sqorz does not publish them.

Stdlib only. No dependency on the rest of this repo -- copy this one file to
a laptop that doesn't have BBS installed and it still works.

Usage:
    # If you already know the scoring computer's IP:
    python sqorz_probe.py --host 192.168.1.50

    # If you don't -- scan your subnet for an open port 4343:
    python sqorz_probe.py --scan 192.168.1.0/24

Every call's raw response is written verbatim to a timestamped folder next
to this script (or --out-dir), one file per function, so nothing has to be
read off the screen to be useful later.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_PORT = 4343
DEFAULT_TIMEOUT = 3.0
SCAN_TIMEOUT = 0.35

# (function name, argument shape) -- from Sqorz's documented LAN API.
# classCode/phaseBlockCode are placeholders; the script tries to replace
# them with real values discovered from getPhaseBlockSummaries first.
FUNCTIONS: list[tuple[str, list]] = [
    ("getEventSummary", []),
    ("getPhaseBlockSummaries", []),
    ("getPhaseSummaries", []),
    (
        "getRaceDetails",
        [{"classCode": "7X_SP", "phaseBlockCode": "M1", "identifyBestTimes": True}],
    ),
    (
        "getPhaseRankDetail",
        [
            {
                "classCode": "7X_SP",
                "phaseBlockCode": "M1",
                "includePhasesWith": "draws",
                "includeTeamName": True,
            }
        ],
    ),
]


def is_port_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_subnet(cidr: str, port: int, timeout: float) -> list[str]:
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(addr) for addr in network.hosts()]
    print(f"Scanning {len(hosts)} addresses in {cidr} for open port {port} ...")
    found: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(is_port_open, host, port, timeout): host for host in hosts}
        checked = 0
        for future in concurrent.futures.as_completed(futures):
            checked += 1
            if checked % 50 == 0:
                print(f"  ... {checked}/{len(hosts)} checked")
            if future.result():
                found.append(futures[future])
    return sorted(found, key=lambda ip: tuple(int(part) for part in ip.split(".")))


def call_function(host: str, port: int, func: str, args: list, timeout: float) -> dict:
    url = f"http://{host}:{port}/api?func={func}"
    body = json.dumps(args).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    result = {"function": func, "args": args, "url": url}
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            result["http_status"] = response.status
            result["raw_text"] = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(result["raw_text"])
                result["ok"] = True
                result["top_level_keys"] = (
                    sorted(parsed.keys())
                    if isinstance(parsed, dict)
                    else f"<list of {len(parsed)}>" if isinstance(parsed, list) else str(type(parsed))
                )
                result["parsed"] = parsed
            except json.JSONDecodeError as exc:
                result["ok"] = True
                result["top_level_keys"] = f"<not JSON: {exc}>"
                result["parsed"] = None
    except HTTPError as exc:
        result["ok"] = False
        result["http_status"] = exc.code
        result["raw_text"] = exc.read().decode("utf-8", errors="replace")
        result["top_level_keys"] = None
        result["parsed"] = None
    except (URLError, TimeoutError, OSError) as exc:
        result["ok"] = False
        result["http_status"] = None
        result["raw_text"] = str(exc)
        result["top_level_keys"] = None
        result["parsed"] = None
    return result


def guess_real_args(phase_block_summaries_result: dict) -> dict | None:
    """Best-effort: pull a real {classCode, phaseBlockCode} pair out of
    getPhaseBlockSummaries's response so getRaceDetails/getPhaseRankDetail
    are called with arguments that might actually match something, instead
    of the placeholder class code. Returns None if nothing plausible found.
    """
    parsed = phase_block_summaries_result.get("parsed")
    candidates = []
    if isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                candidates = value
                break
    for item in candidates:
        if not isinstance(item, dict):
            continue
        class_code = item.get("classCode")
        phase_block_code = item.get("phaseBlockCode") or item.get("phaseCode")
        if class_code and phase_block_code:
            return {"classCode": class_code, "phaseBlockCode": phase_block_code}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", help="Sqorz scoring computer's IP or hostname.")
    parser.add_argument("--scan", metavar="CIDR", help="Scan a subnet for an open Sqorz port, e.g. 192.168.1.0/24.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"LAN API port (default {DEFAULT_PORT}).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Per-call timeout in seconds (default {DEFAULT_TIMEOUT}).")
    parser.add_argument("--out-dir", help="Where to write raw responses (default: timestamped folder next to this script).")
    args = parser.parse_args()

    if not args.host and not args.scan:
        parser.error("pass --host <ip> or --scan <cidr>")

    host = args.host
    if args.scan:
        found = scan_subnet(args.scan, args.port, SCAN_TIMEOUT)
        if not found:
            print(f"\nNo host in {args.scan} has port {args.port} open. Is the scoring computer on this network?")
            return 1
        print(f"\nFound {len(found)} host(s) with port {args.port} open: {', '.join(found)}")
        host = host or found[0]
        if len(found) > 1:
            print(f"Using the first one ({host}). Pass --host explicitly to use a different one.")

    print(f"\nProbing Sqorz LAN API at {host}:{args.port} (timeout {args.timeout}s per call)\n")

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).resolve().parent / (
        "sqorz-probe-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    reachable_count = 0
    for func, default_args in FUNCTIONS:
        call_args = default_args
        if func in ("getRaceDetails", "getPhaseRankDetail"):
            guessed = guess_real_args(results.get("getPhaseBlockSummaries", {}))
            if guessed:
                call_args = [{**default_args[0], **guessed}]

        result = call_function(host, args.port, func, call_args, args.timeout)
        results[func] = result

        status_word = "OK" if result["ok"] else "FAIL"
        if result["ok"]:
            reachable_count += 1
        print(f"[{status_word}] {func}")
        print(f"        args:   {json.dumps(call_args)}")
        print(f"        status: {result.get('http_status')}")
        print(f"        keys:   {result.get('top_level_keys')}")
        if not result["ok"]:
            print(f"        error:  {result.get('raw_text')}")
        print()

        response_file = out_dir / f"{func}.json"
        response_file.write_text(
            json.dumps(
                {
                    "function": func,
                    "args": call_args,
                    "http_status": result.get("http_status"),
                    "raw_text": result.get("raw_text"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"Reached {reachable_count}/{len(FUNCTIONS)} functions.")
    print(f"Raw responses saved to: {out_dir}")
    if reachable_count == 0:
        print("\nNothing responded. Check the scoring computer is on this network and Sqorz is running.")
        return 1
    print(
        "\nSend the saved files back so connector/services/sqorz_service.py's "
        "LAN parsing (currently best-effort/UNVERIFIED) can be finished "
        "against the real shapes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
