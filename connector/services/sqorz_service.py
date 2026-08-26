"""Read-only Sqorz live-timing client: internet, LAN, or a saved file, never fatal.

Sqorz supplies rider TIMES only. It never sets a round/phase label -- BBS
decides "Round 1"/"Moto 3"/"Main" from RaceManager's own class finalization
method (see docs/racemanager-round-model.md and CLAUDE.md). Nothing in this
module should ever be treated as a phase label.

Follows the stdlib urllib pattern already used by connector/service_status.py
-- no new runtime dependency. All three backends use a short timeout (file
mode: none needed), cache the last good payload in memory, and are polled no
more often than the configured interval; a failed fetch serves the cache
(marked stale) instead of raising, so an optional, unreachable, or slow Sqorz
never fails a request.

"file" mode (BBS_SQORZ_MODE=file) replays a payload saved with
scripts/sqorz_capture.py through the exact same parse_event_payload() used by
internet mode -- only the fetch differs, so it's a genuine demo of real data
with no network at all, for when neither the venue's LAN nor internet is
available.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SqorzRiderTime:
    """One competitor's result for one phase, normalised from Sqorz's shape."""

    class_code: str | None
    class_name: str | None
    plate: str | None
    first_name: str | None
    last_name: str | None
    transponder: str | None
    phase_code: str
    phase_name: str | None
    time_seconds: float | None
    time_raw: str | None
    race_position: int | None
    rank: int | None
    # Sqorz's own finish position for this phase, straight from the `result`
    # key -- NOT `racePosition` (starting gate) and NOT `rank` (overall
    # class standing, not per-race). Carries internal status codes for
    # anything other than a placed finish (100400 and 103000 both confirmed
    # live); callers must run this through plausible_finish() before
    # display, never invent a DNF/DNS/DQ label from it.
    result: int | None = None
    # Class-level metadata (same for every row of the same class), used only
    # by the standalone Sqorz overlay's "most recently updated" default --
    # see connector/services/sqorz_overlay_service.py. Optional/defaulted so
    # existing SqorzRiderTime(...) call sites are unaffected.
    class_timestamp: str | None = None
    class_rank_phase_code: str | None = None


@dataclass
class SqorzFetchResult:
    riders: list[SqorzRiderTime]
    reachable: bool
    stale: bool
    age_seconds: float | None
    error: str | None = None


def _parse_time(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# A BMX moto/main plates 8 riders max; anything outside 1-8 in Sqorz's
# `result` field is a status code (100400 and 103000 both confirmed live on
# withdrawn/no-show riders), never a real finish position.
_PLAUSIBLE_FINISH_POSITIONS = range(1, 9)


def plausible_finish(result: int | None) -> int | None:
    """Sqorz's `result` field as a displayable finish, or None.

    Renders exactly like a missing time when the value isn't a plausible
    1-8 finish -- never guesses a DNF/DNS/DQ label from an internal status
    code we don't have documentation for.
    """
    if result is None or result not in _PLAUSIBLE_FINISH_POSITIONS:
        return None
    return result


def parse_event_payload(payload: dict[str, Any]) -> list[SqorzRiderTime]:
    """Flatten Sqorz's classRanks[].competitorRankSummaries[].competitorRankDetails[]
    into one SqorzRiderTime per rider per phase. Tolerates missing/unexpected
    fields -- a malformed entry is skipped, never raised.
    """
    rows: list[SqorzRiderTime] = []
    for class_rank in payload.get("classRanks") or []:
        if not isinstance(class_rank, dict):
            continue
        class_code = class_rank.get("classCode")
        class_name = class_rank.get("className")
        class_timestamp = class_rank.get("timestamp")
        class_rank_phase_code = class_rank.get("rankPhaseCode")
        for competitor in class_rank.get("competitorRankSummaries") or []:
            if not isinstance(competitor, dict):
                continue
            for detail in competitor.get("competitorRankDetails") or []:
                if not isinstance(detail, dict):
                    continue
                phase_code = detail.get("phaseCode")
                if not phase_code:
                    continue
                raw_time = detail.get("time")
                rows.append(
                    SqorzRiderTime(
                        class_code=class_code,
                        class_name=class_name,
                        plate=competitor.get("plate"),
                        first_name=competitor.get("firstName"),
                        last_name=competitor.get("lastName"),
                        transponder=competitor.get("transponder"),
                        phase_code=phase_code,
                        phase_name=detail.get("phaseName"),
                        time_seconds=_parse_time(raw_time),
                        time_raw=raw_time if isinstance(raw_time, str) else None,
                        race_position=_parse_int(detail.get("racePosition")),
                        rank=_parse_int(detail.get("rank")),
                        result=_parse_int(detail.get("result")),
                        class_timestamp=(
                            class_timestamp if isinstance(class_timestamp, str) else None
                        ),
                        class_rank_phase_code=(
                            class_rank_phase_code if isinstance(class_rank_phase_code, str) else None
                        ),
                    )
                )
    return rows


def _first_list(payload: Any, *keys: str) -> list[Any]:
    """Best-effort extraction for the undocumented LAN response shapes.

    Sqorz does not publish these -- try a few plausible container keys and
    fall back to treating the payload itself as the list. Returns [] rather
    than raising when nothing matches.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def parse_lan_phase_rank_detail(
    payload: Any, *, class_code: str | None, class_name: str | None
) -> list[SqorzRiderTime]:
    """Best-effort parse of getPhaseRankDetail's response.

    UNVERIFIED: Sqorz has not published this shape. Written defensively,
    assuming a structure similar to the internet API's competitor/detail
    rows, on the theory that both surfaces come from the same underlying
    data model. Confirm the real shape on site with scripts/sqorz_probe.py
    and adjust the candidate keys below once captured -- until then this
    tolerates being wrong by returning [] rather than raising.
    """
    rows: list[SqorzRiderTime] = []
    for competitor in _first_list(payload, "competitors", "rankDetails", "results", "data"):
        if not isinstance(competitor, dict):
            continue
        details = competitor.get("competitorRankDetails")
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                phase_code = detail.get("phaseCode") or class_code
                if not phase_code:
                    continue
                raw_time = detail.get("time")
                rows.append(
                    SqorzRiderTime(
                        class_code=class_code,
                        class_name=class_name,
                        plate=competitor.get("plate"),
                        first_name=competitor.get("firstName"),
                        last_name=competitor.get("lastName"),
                        transponder=competitor.get("transponder"),
                        phase_code=phase_code,
                        phase_name=detail.get("phaseName"),
                        time_seconds=_parse_time(raw_time),
                        time_raw=raw_time if isinstance(raw_time, str) else None,
                        race_position=_parse_int(detail.get("racePosition")),
                        rank=_parse_int(detail.get("rank")),
                        result=_parse_int(detail.get("result")),
                    )
                )
            continue
        # Flat shape: one row per competitor already scoped to one phase.
        phase_code = competitor.get("phaseCode") or class_code
        if not phase_code:
            continue
        raw_time = competitor.get("time")
        rows.append(
            SqorzRiderTime(
                class_code=class_code,
                class_name=class_name,
                plate=competitor.get("plate"),
                first_name=competitor.get("firstName"),
                last_name=competitor.get("lastName"),
                transponder=competitor.get("transponder"),
                phase_code=phase_code,
                phase_name=competitor.get("phaseName"),
                time_seconds=_parse_time(raw_time),
                time_raw=raw_time if isinstance(raw_time, str) else None,
                race_position=_parse_int(competitor.get("racePosition")),
                rank=_parse_int(competitor.get("rank")),
                result=_parse_int(competitor.get("result")),
            )
        )
    return rows


class SqorzService:
    """Poll Sqorz (internet or LAN) with a short timeout and a last-good cache.

    A single instance is shared for the life of the process (see
    connector/dependencies.py); ``last_match_report``/``last_match_class_name``/
    ``last_match_class_alias`` are written by CurrentLineupService after each
    match so the diagnostics endpoint and /sqorz-match-report page have
    something to report without needing their own copy of the match logic.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        mode: str = "internet",
        event_id: str = "",
        org_code: str = "",
        host: str = "",
        port: int = 4343,
        file_path: str = "",
        poll_seconds: float = 10.0,
        timeout_seconds: float = 2.0,
        clock: Any = time.monotonic,
    ) -> None:
        self.enabled = enabled
        self.mode = mode
        self.event_id = event_id
        self.org_code = org_code
        self.host = host
        self.port = port
        self.file_path = file_path
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self._cache: list[SqorzRiderTime] = []
        self._cached_at: float | None = None
        self._last_fetch_attempt: float | None = None
        self._last_error: str | None = None
        self.last_match_report: Any = None
        self.last_match_class_name: str | None = None
        self.last_match_class_alias: str | None = None

    def get_riders(self) -> SqorzFetchResult:
        if not self.enabled:
            return SqorzFetchResult(riders=[], reachable=False, stale=False, age_seconds=None)

        now = self._clock()
        due = (
            self._last_fetch_attempt is None
            or (now - self._last_fetch_attempt) >= self.poll_seconds
        )
        if due:
            self._last_fetch_attempt = now
            try:
                self._cache = self._fetch()
                self._cached_at = now
                self._last_error = None
            except Exception as exc:  # noqa: BLE001 -- Sqorz must never be fatal
                self._last_error = str(exc)

        if self._cached_at is None:
            return SqorzFetchResult(
                riders=[],
                reachable=False,
                stale=False,
                age_seconds=None,
                error=self._last_error,
            )
        age = now - self._cached_at
        return SqorzFetchResult(
            riders=self._cache,
            reachable=self._last_error is None,
            stale=age > (self.poll_seconds * 3),
            age_seconds=age,
            error=self._last_error,
        )

    def _fetch(self) -> list[SqorzRiderTime]:
        if self.mode == "lan":
            return self._fetch_lan()
        if self.mode == "file":
            return self._fetch_file()
        return self._fetch_internet()

    def _fetch_internet(self) -> list[SqorzRiderTime]:
        if not self.event_id:
            raise ValueError("BBS_SQORZ_EVENT_ID is not configured.")
        payload = self._get_json(f"https://our.sqorz.com/json/event/{self.event_id}")
        return parse_event_payload(payload)

    def _fetch_file(self) -> list[SqorzRiderTime]:
        """Replay a payload saved with scripts/sqorz_capture.py.

        Through the exact same parse_event_payload() internet mode uses --
        only the fetch differs, so this is a genuine demo of real data with
        no network involved at all.
        """
        if not self.file_path:
            raise ValueError("BBS_SQORZ_FILE_PATH is not configured.")
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Sqorz replay file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return parse_event_payload(payload)

    def _fetch_lan(self) -> list[SqorzRiderTime]:
        # UNVERIFIED end to end -- see parse_lan_phase_rank_detail. This calls
        # the documented function signatures; the response shapes are not
        # documented by Sqorz and must be confirmed on site.
        blocks = self._call_lan("getPhaseBlockSummaries", [])
        rows: list[SqorzRiderTime] = []
        for block in _first_list(blocks, "phaseBlockSummaries", "blocks", "data"):
            if not isinstance(block, dict):
                continue
            class_code = block.get("classCode")
            phase_block_code = block.get("phaseBlockCode")
            if not class_code or not phase_block_code:
                continue
            detail_payload = self._call_lan(
                "getPhaseRankDetail",
                [
                    {
                        "classCode": class_code,
                        "phaseBlockCode": phase_block_code,
                        "includePhasesWith": "draws",
                        "includeTeamName": True,
                    }
                ],
            )
            rows.extend(
                parse_lan_phase_rank_detail(
                    detail_payload,
                    class_code=class_code,
                    class_name=block.get("className"),
                )
            )
        return rows

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "BBS-Sqorz/1.0"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)

    def _call_lan(self, func: str, args: list[Any]) -> Any:
        if not self.host:
            raise ValueError("BBS_SQORZ_HOST is not configured.")
        url = f"http://{self.host}:{self.port}/api?func={func}"
        body = json.dumps(args).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)
