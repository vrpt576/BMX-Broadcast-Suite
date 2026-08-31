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

LAN mode's response shapes are UNVERIFIED -- Sqorz has never published them.
parse_lan_phase_rank_detail() tries a shape guessed from the verified
internet API first; parse_lan_by_searching_the_tree() is a resilience
fallback for when that guess doesn't match, searching the whole response for
recognisable field names regardless of nesting. Neither is proof the real
shape is understood -- that's RESILIENCE, not verification. See
docs/sqorz-live-timing.md and scripts/sqorz_probe.py.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
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


@dataclass(frozen=True)
class SqorzEventSummary:
    """One event from /json/org/{orgCode} -- verified real shape (see
    tests/fixtures/sqorz/usabmx_org.json), used only for the internet-mode
    event picker (Sqorz-only mode, Change 3). Deliberately just the three
    fields a picker needs, not every field that payload carries."""

    event_id: str
    event_name: str
    event_date: str | None


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


def parse_org_events_payload(payload: dict[str, Any]) -> list[SqorzEventSummary]:
    """Verified shape: payload["events"] is a list of dicts carrying
    eventId/eventName/eventDate, confirmed against a real captured
    /json/org/{orgCode} response (tests/fixtures/sqorz/usabmx_org.json).
    Skips any entry missing an eventId or eventName rather than raising --
    same tolerance as parse_event_payload()."""
    summaries: list[SqorzEventSummary] = []
    for entry in payload.get("events") or []:
        if not isinstance(entry, dict):
            continue
        event_id = entry.get("eventId")
        event_name = entry.get("eventName")
        if not event_id or not event_name:
            continue
        event_date = entry.get("eventDate")
        summaries.append(
            SqorzEventSummary(
                event_id=event_id,
                event_name=event_name,
                event_date=event_date if isinstance(event_date, str) else None,
            )
        )
    return summaries


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


# ---------------------------------------------------------------------------
# Tree-search fallback for LAN mode: resilience, not verification.
#
# parse_lan_phase_rank_detail() below assumes one specific guessed nesting.
# When that guess is wrong, the functions in this section instead walk the
# ENTIRE response tree, at any depth, looking for dicts that carry
# recognisable field names -- so a response shaped differently than guessed
# can still yield real riders. They deliberately recognise ONLY the exact
# field vocabulary the verified internet API uses (case/underscore
# variations aside), never a broader set of guessed synonyms: a wrong
# synonym guess could misattribute a value to the wrong meaning (e.g.
# confusing `result` -- finish position -- with `racePosition` -- starting
# gate; the two are never interchangeable, see sqorz_matching.py), which is
# worse than finding nothing. A match here is not proof the real LAN
# contract is understood, only that something with a known field name was
# found somewhere in the response.
# ---------------------------------------------------------------------------


def _walk_dicts(node: Any) -> Iterator[dict[str, Any]]:
    """Every dict anywhere in a JSON-shaped tree, depth-first (including the
    node itself). Used only by the tree-search fallback below."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_dicts(item)


def _normalize_key(key: str) -> str:
    return key.replace("_", "").replace("-", "").lower()


# canonical field -> the one normalised key it's recognised by.
_TREE_SEARCH_KEYS: dict[str, str] = {
    "plate": "plate",
    "first_name": "firstname",
    "last_name": "lastname",
    "transponder": "transponder",
    "class_code": "classcode",
    "class_name": "classname",
    "phase_code": "phasecode",
    "phase_block_code": "phaseblockcode",
    "phase_name": "phasename",
    "time": "time",
    "race_position": "raceposition",
    "rank": "rank",
    "result": "result",
}


def _tree_search_find(d: dict[str, Any], field: str) -> Any:
    target = _TREE_SEARCH_KEYS[field]
    for key, value in d.items():
        if _normalize_key(key) == target:
            return value
    return None


def _looks_like_a_phase_block(d: dict[str, Any]) -> bool:
    return _tree_search_find(d, "class_code") is not None and (
        _tree_search_find(d, "phase_block_code") is not None
        or _tree_search_find(d, "phase_code") is not None
    )


def find_phase_blocks_by_searching_the_tree(payload: Any) -> list[dict[str, Any]]:
    """Resilience fallback for getPhaseBlockSummaries: when _first_list's
    guessed container keys find nothing, search the whole response for
    dicts that look like a (classCode, phaseBlockCode) pair instead."""
    blocks: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for candidate in _walk_dicts(payload):
        if not _looks_like_a_phase_block(candidate):
            continue
        class_code = _tree_search_find(candidate, "class_code")
        phase_block_code = _tree_search_find(candidate, "phase_block_code") or _tree_search_find(
            candidate, "phase_code"
        )
        key = (class_code, phase_block_code)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(
            {
                "classCode": class_code,
                "className": _tree_search_find(candidate, "class_name"),
                "phaseBlockCode": phase_block_code,
            }
        )
    return blocks


def _looks_like_a_competitor(d: dict[str, Any]) -> bool:
    return _tree_search_find(d, "last_name") is not None or _tree_search_find(d, "plate") is not None


def _looks_like_a_phase_detail(d: dict[str, Any]) -> bool:
    return (
        _tree_search_find(d, "time") is not None
        or _tree_search_find(d, "result") is not None
        or _tree_search_find(d, "phase_code") is not None
    )


def _iter_candidate_records(payload: Any) -> Iterator[dict[str, Any]]:
    """Every list-item dict found anywhere in the tree is a candidate "one
    rider's record" boundary -- a list is the natural signal of "multiple
    repeated entries" in a JSON API, so each item is treated as everything
    about one rider, however its own internals happen to be arranged. If
    the payload has no list in it anywhere, it's inherently a single record
    already (nothing else for it to be confused with), so it's yielded on
    its own instead.
    """
    found_a_list = False
    if isinstance(payload, (dict, list)):
        for node in _walk_dicts(payload):
            for value in node.values():
                if isinstance(value, list):
                    found_a_list = True
                    for item in value:
                        if isinstance(item, dict):
                            yield item
    if isinstance(payload, list):
        found_a_list = True
        for item in payload:
            if isinstance(item, dict):
                yield item
    if not found_a_list and isinstance(payload, dict):
        yield payload


def parse_lan_by_searching_the_tree(
    payload: Any, *, class_code: str | None, class_name: str | None
) -> list[SqorzRiderTime]:
    """Last-resort fallback when parse_lan_phase_rank_detail's guessed shape
    matches nothing. For each candidate record (see _iter_candidate_records
    above), searches its own subtree for a name/plate to use as the rider's
    identity, then pairs that identity with every phase-detail-looking dict
    (a time, result, or phase code) found anywhere else within that SAME
    record -- covering both a detail nested inside a competitor object
    (competitor.details) and a detail that's merely a sibling of one under
    a shared wrapper ({"rider": {...}, "results": [...]}), without assuming
    which of those two shapes it is. See the module section docstring above
    for what this does and does not prove.
    """
    rows: list[SqorzRiderTime] = []
    for record in _iter_candidate_records(payload):
        subtree = list(_walk_dicts(record))
        identity_source = next((d for d in subtree if _looks_like_a_competitor(d)), None)
        if identity_source is None:
            continue
        plate = _tree_search_find(identity_source, "plate")
        first_name = _tree_search_find(identity_source, "first_name")
        last_name = _tree_search_find(identity_source, "last_name")
        transponder = _tree_search_find(identity_source, "transponder")

        for detail in subtree:
            if not _looks_like_a_phase_detail(detail):
                continue
            phase_code = _tree_search_find(detail, "phase_code") or class_code
            if not phase_code:
                continue
            raw_time = _tree_search_find(detail, "time")
            rows.append(
                SqorzRiderTime(
                    class_code=_tree_search_find(detail, "class_code") or class_code,
                    class_name=_tree_search_find(detail, "class_name") or class_name,
                    plate=plate,
                    first_name=first_name,
                    last_name=last_name,
                    transponder=transponder,
                    phase_code=str(phase_code),
                    phase_name=_tree_search_find(detail, "phase_name"),
                    time_seconds=_parse_time(raw_time),
                    time_raw=raw_time if isinstance(raw_time, str) else None,
                    race_position=_parse_int(_tree_search_find(detail, "race_position")),
                    rank=_parse_int(_tree_search_find(detail, "rank")),
                    result=_parse_int(_tree_search_find(detail, "result")),
                )
            )

    seen: set[tuple[Any, Any, Any, str]] = set()
    deduped: list[SqorzRiderTime] = []
    for row in rows:
        key = (row.plate, row.first_name, row.last_name, row.phase_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def parse_lan_phase_summaries_order(payload: Any) -> list[tuple[str | None, str | None]]:
    """UNVERIFIED, like the rest of LAN parsing: Sqorz's own API docs
    describe getPhaseSummaries as listing races in running order, but no
    real payload has ever been captured to confirm the response shape (see
    scripts/sqorz_probe.py -- it asks the question; nothing has sent an
    answer back yet). Assumes the response is, or contains, a list of
    entries in that order, each carrying a classCode and a
    phaseCode/phaseBlockCode -- tries a guessed container key first, then
    falls back to searching the whole tree for anything phase-block-shaped,
    exactly like getPhaseBlockSummaries's own fallback above.

    Returns [] rather than raising when nothing recognisable is found --
    connector/services/sqorz_navigation_service.py treats an empty order as
    "no verified ordering available" and falls back to a deterministic
    (alphabetical class, canonical phase) ordering instead of inventing one.
    An empty result here is not proof the ordering guess is wrong, only that
    this specific response didn't match it -- same caveat as everywhere else
    in LAN parsing.
    """
    entries = _first_list(payload, "phaseSummaries", "summaries", "data")
    if not entries:
        entries = [item for item in _walk_dicts(payload) if _looks_like_a_phase_block(item)]

    order: list[tuple[str | None, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        class_code = item.get("classCode") or _tree_search_find(item, "class_code")
        phase_code = (
            item.get("phaseCode")
            or item.get("phaseBlockCode")
            or _tree_search_find(item, "phase_code")
            or _tree_search_find(item, "phase_block_code")
        )
        if class_code is None and phase_code is None:
            continue
        key = (class_code, phase_code)
        if key in seen:
            continue
        seen.add(key)
        order.append(key)
    return order


def _has_any_content(raw_responses: dict[str, Any]) -> bool:
    return any(value not in (None, {}, []) for value in raw_responses.values())


def parse_lan_phase_rank_detail(
    payload: Any, *, class_code: str | None, class_name: str | None
) -> list[SqorzRiderTime]:
    """Best-effort parse of getPhaseRankDetail's response.

    UNVERIFIED: Sqorz has not published this shape. Written defensively,
    assuming a structure similar to the internet API's competitor/detail
    rows, on the theory that both surfaces come from the same underlying
    data model. Confirm the real shape on site with scripts/sqorz_probe.py
    and adjust the candidate keys below once captured -- until then this
    tolerates being wrong by returning [] rather than raising. See
    parse_lan_by_searching_the_tree() above for the fallback SqorzService
    tries when this guess matches nothing.
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
        raw_response_file: Path | None = None,
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
        # Where the raw LAN response is saved when parsing yields nothing
        # usable -- see _fetch_lan(). None disables the disk save (still
        # kept in memory via last_raw_lan_response either way).
        self.raw_response_file = raw_response_file
        self._clock = clock
        self._cache: list[SqorzRiderTime] = []
        self._cached_at: float | None = None
        self._last_fetch_attempt: float | None = None
        self._last_error: str | None = None
        self.last_match_report: Any = None
        self.last_match_class_name: str | None = None
        self.last_match_class_alias: str | None = None
        # LAN mode only -- the most recent raw response(s), kept in memory
        # regardless of whether parsing found anything, so a status page can
        # show them without a terminal. See connector/routes/sqorz_status.py.
        self.last_raw_lan_response: dict[str, Any] | None = None
        # Set only when LAN responded but nothing recognisable was found in
        # it -- never set for "reachable, genuinely nothing racing yet".
        self.last_lan_parse_warning: str | None = None
        # LAN mode only -- getPhaseSummaries's guessed running order, as
        # (classCode, phaseCode) pairs. Empty means "no verified ordering
        # available this poll" (getPhaseSummaries failed, or its shape
        # didn't match) -- see parse_lan_phase_summaries_order() and
        # connector/services/sqorz_navigation_service.py, which falls back
        # to a deterministic ordering when this is empty rather than
        # treating an empty list as "no races".
        self.last_phase_summaries_order: list[tuple[str | None, str | None]] = []

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

    def fetch_org_events(self) -> list[SqorzEventSummary]:
        """The internet-mode event picker's data source (Sqorz-only mode,
        Change 3) -- a real, on-demand call, not part of the polled
        get_riders() cache cycle, since an operator picking a different
        event is a rare, deliberate action, not something to re-fetch every
        few seconds. Requires self.org_code (BBS_SQORZ_ORG_CODE); returns
        [] rather than raising when unconfigured, unreachable, or the
        response doesn't parse -- same never-fatal contract as everything
        else in this class."""
        if not self.org_code:
            return []
        try:
            payload = self._get_json(f"https://our.sqorz.com/json/org/{self.org_code}")
            return parse_org_events_payload(payload)
        except Exception:  # noqa: BLE001 - an event list is optional, never fatal
            return []

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
        # UNVERIFIED end to end -- the response shapes are not documented by
        # Sqorz. This calls the documented function signatures; parsing
        # tries the guessed shape first, falling back to the tree-search
        # resilience path when that finds nothing -- see
        # parse_lan_phase_rank_detail/parse_lan_by_searching_the_tree above.
        raw_responses: dict[str, Any] = {}

        # Ordering only -- deliberately its own try/except, isolated from
        # the rider-time fetch below. getPhaseSummaries is a second,
        # separate LAN call; an older Sqorz version without it, or a shape
        # this parser doesn't recognise, must degrade to "no verified
        # ordering this poll" and nothing more -- it must never take rider
        # times down with it.
        try:
            summaries_response = self._call_lan("getPhaseSummaries", [])
            raw_responses["getPhaseSummaries"] = summaries_response
            self.last_phase_summaries_order = parse_lan_phase_summaries_order(summaries_response)
        except Exception:  # noqa: BLE001 - ordering is best-effort, never fatal
            self.last_phase_summaries_order = []

        blocks_response = self._call_lan("getPhaseBlockSummaries", [])
        raw_responses["getPhaseBlockSummaries"] = blocks_response
        blocks = _first_list(blocks_response, "phaseBlockSummaries", "blocks", "data")
        if not blocks:
            blocks = find_phase_blocks_by_searching_the_tree(blocks_response)

        rows: list[SqorzRiderTime] = []
        for block in blocks:
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
            raw_responses[f"getPhaseRankDetail[{class_code}/{phase_block_code}]"] = detail_payload
            parsed = parse_lan_phase_rank_detail(
                detail_payload, class_code=class_code, class_name=block.get("className")
            )
            if not parsed:
                parsed = parse_lan_by_searching_the_tree(
                    detail_payload, class_code=class_code, class_name=block.get("className")
                )
            rows.extend(parsed)

        self.last_raw_lan_response = raw_responses
        if not rows and _has_any_content(raw_responses):
            self._save_raw_lan_response(raw_responses)
            self.last_lan_parse_warning = (
                "Sqorz LAN responded, but no rider data could be recognised "
                "in the response shape -- this is a parsing gap, not proof "
                "Sqorz has no data yet. Raw response saved to "
                f"{self.raw_response_file}. Send scripts/sqorz_probe.py's "
                "output back so the parser can be finished against the real "
                "shape -- see docs/sqorz-live-timing.md."
            )
        else:
            self.last_lan_parse_warning = None
        return rows

    def _save_raw_lan_response(self, raw_responses: dict[str, Any]) -> None:
        if self.raw_response_file is None:
            return
        try:
            self.raw_response_file.parent.mkdir(parents=True, exist_ok=True)
            self.raw_response_file.write_text(
                json.dumps(raw_responses, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass  # best-effort only -- a disk problem must never break Sqorz polling

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
