#!/usr/bin/env python3
"""Sqorz LAN scoring API probe -- collects real response shapes to send back.

Read-only: it only asks Sqorz's LAN API questions and writes the answers to
a file. It never changes anything in Sqorz, RaceManager, or anywhere else,
and it only talks to Sqorz over the local network -- no internet involved.
See PLAIN_ENGLISH_HEADER below for the full non-technical explanation,
printed at the start of every interactive run.

Developer usage (same file, no repo dependency required):
    python sqorz_probe.py --host 192.168.1.50
    python sqorz_probe.py --scan 192.168.1.0/24
Run with no arguments (or via the "Run Sqorz Probe.bat" launcher it ships
with) for the interactive, double-click-friendly mode -- it prompts for the
scoring computer's IP, or offers to scan the local network for it.

Every call's raw response is written verbatim to a timestamped folder next
to this script (or --out-dir), one file per function, then the whole folder
is zipped up -- so nothing has to be read off the screen to be useful later,
and there is exactly one file to send back.

Stdlib only. No dependency on the rest of this repo -- copy this one file
(or the whole kit it ships in) to a computer that's never seen this project
and it still works.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Who to email the results to. Edit this if you're sending it somewhere else.
CONTACT = "zackcohen86@gmail.com"

PLAIN_ENGLISH_HEADER = f"""\
============================================================================
 WHAT THIS IS (read this part even if you're not a developer)
============================================================================
This tool checks whether the Sqorz scoring software on THIS network can be
reached, and saves a copy of what it says back.

It is READ-ONLY. It never changes anything in Sqorz, RaceManager, or
anywhere else -- it only asks Sqorz questions and writes the answers to a
file. It only talks to Sqorz over this local network; it does not use the
internet and does not send anything anywhere on its own.

What it collects is the same kind of information already shown on Sqorz's
own public results pages for this event -- class and round names, plate
numbers, rider names, and times. It does not collect anything about members
beyond that: no addresses, phone numbers, birthdates, or payment details.

HOW TO RUN IT: double-click "Run Sqorz Probe.bat" in this same folder (or,
if you only have this one .py file, see "Developer usage" in --help).
Answer the one or two questions it asks. When it finishes, it creates a
.zip file in this folder -- please email that .zip file to:

    {CONTACT}

That's the whole job. Thank you for running this.
============================================================================
"""

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

# Plain-English names for the header/summary -- FUNCTIONS above keeps the
# real Sqorz function names, which is what matters for the actual probe.
FRIENDLY_NAMES = {
    "getEventSummary": "basic event information",
    "getPhaseBlockSummaries": "the list of classes and rounds",
    "getPhaseSummaries": "a summary of each round",
    "getRaceDetails": "details for one race",
    "getPhaseRankDetail": "rider names, plates, and times for one round",
}


def is_port_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_subnet(cidr: str, port: int, timeout: float) -> list[str]:
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = [str(addr) for addr in network.hosts()]
    print(f"Scanning {len(hosts)} addresses on {cidr} for the scoring computer ...")
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


def detect_local_subnet() -> str | None:
    """Best-effort local /24, from whichever network interface would be used
    to leave this machine -- no packets are actually sent (UDP "connect"
    just picks a route), so this works even with no real internet access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            local_ip = probe.getsockname()[0]
        octets = local_ip.split(".")
        if len(octets) == 4:
            return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
    except OSError:
        pass
    return None


def prompt_for_host(port: int) -> str | None:
    """Interactive, non-technical flow: ask for an IP, or offer to find it."""
    if not sys.stdin.isatty():
        return None
    print("Do you know the scoring computer's IP address?")
    typed = input("If so, type it now (or just press Enter to search for it): ").strip()
    if typed:
        return typed

    subnet = detect_local_subnet()
    if subnet is None:
        print("\nCouldn't automatically figure out this network.")
        return input("Please ask whoever runs Sqorz for the scoring computer's IP address: ").strip() or None

    found = scan_subnet(subnet, port, SCAN_TIMEOUT)
    if not found:
        print(f"\nNothing found on {subnet}. Make sure you're on the same WiFi/network as Sqorz.")
        return input("You can also type the IP address directly here: ").strip() or None
    if len(found) == 1:
        print(f"Found it: {found[0]}")
        return found[0]
    print(f"\nFound {len(found)} possible matches: {', '.join(found)}")
    chosen = input(f"Which one is the Sqorz scoring computer? [{found[0]}]: ").strip()
    return chosen or found[0]


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


def _count_items(parsed: object) -> int | None:
    """Best-effort item count for the plain-English summary line only --
    not used for anything the real parser relies on."""
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                return len(value)
    return None


def friendly_failure_reason(result: dict) -> str:
    status = result.get("http_status")
    text = (result.get("raw_text") or "").lower()
    if status is None:
        if "timed out" in text:
            return "It didn't answer in time -- it may be busy, or this may be the wrong address."
        return "Couldn't connect at all -- double check the address and that Sqorz is running."
    if status == 404:
        return "This feature doesn't seem to exist here -- that's OK, not every setup has it."
    return f"It answered, but with an error (HTTP {status})."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", help="Sqorz scoring computer's IP or hostname.")
    parser.add_argument("--scan", metavar="CIDR", help="Scan a subnet for an open Sqorz port, e.g. 192.168.1.0/24.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"LAN API port (default {DEFAULT_PORT}).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Per-call timeout in seconds (default {DEFAULT_TIMEOUT}).")
    parser.add_argument("--out-dir", help="Where to write raw responses (default: timestamped folder next to this script).")
    parser.add_argument("--no-header", action="store_true", help="Skip the plain-language header (for scripted/developer use).")
    args = parser.parse_args()

    if not args.no_header:
        print(PLAIN_ENGLISH_HEADER)

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
    elif not host:
        host = prompt_for_host(args.port)
        if not host:
            print("\nNo address given -- nothing to check. Run this again with an IP address handy.")
            return 1

    print(f"\nChecking Sqorz at {host}:{args.port} ...\n")

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
        friendly = FRIENDLY_NAMES.get(func, func)

        if result["ok"]:
            reachable_count += 1
            count = _count_items(result.get("parsed"))
            extra = "" if count is None else f" Found {count} item(s)." if count else " Looks empty right now."
            print(f"  YES -- got {friendly} ({func}).{extra}")
        else:
            print(f"  NO  -- couldn't get {friendly} ({func}). {friendly_failure_reason(result)}")

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

    print(f"\n{reachable_count}/{len(FUNCTIONS)} questions got an answer.")

    zip_path = Path(shutil.make_archive(str(out_dir), "zip", root_dir=out_dir.parent, base_dir=out_dir.name))
    print(f"\nEverything has been saved and zipped up here:\n  {zip_path}")

    if reachable_count == 0:
        print(
            "\nNothing answered at all. Double-check the address, that Sqorz is "
            "running, and that this computer is on the same network as it. "
            f"You can still send the .zip above to {CONTACT} -- even an empty "
            "result is useful information."
        )
        return 1

    print(f"\nPlease email that .zip file to {CONTACT}. That's everything -- thank you!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
