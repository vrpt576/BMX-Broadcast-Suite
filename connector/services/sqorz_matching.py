"""Match RaceManager riders to Sqorz competitors -- never guess a time.

Sqorz identifies a competitor by plate/name; RaceManager identifies a rider
by bike number/name. There is no shared ID, so every match carries an
explicit confidence tier, and only the two most trustworthy tiers are ever
allowed to put a time on air:

  exact  -- plate matches bike_number AND last name matches (normalised)
  strong -- plate matches bike_number within the same resolved class
  weak   -- last name + first initial match within the same class
  none   -- anything else

"weak" is recorded in the match report (useful for diagnosing a class that
isn't lining up at the track) but never produces a displayed time. Guessing
is worse than showing nothing.

Plate is not unique, on either side. USA BMX district plates collide
constantly within one class (confirmed live: Hoosier's "11-12 Open" has both
Dylan Dobelle and Wade Hinderlider on plate 9), and nothing stops two
RaceManager riders in one class from sharing a bike number either. A "strong"
match relies on plate alone, so it is only trusted when the plate is unique
on BOTH sides within the resolved class -- an ambiguous plate never reaches
"strong"; it can still reach "exact" if the last name also matches (which
disambiguates on its own), otherwise it falls to "weak" (never displayed).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from connector.models import RacePhase
from connector.services.sqorz_service import SqorzRiderTime

# BBS's own round -> the Sqorz phaseCode that carries that round's time.
# Never the reverse: a Sqorz phase name must never reach a phase_label or a
# RaceStage.label (see docs/racemanager-round-model.md and CLAUDE.md --
# RaceManager's finalization method, not Sqorz, decides Moto 3 vs Main).
ROUND_PHASE_TO_SQORZ_CODE: dict[RacePhase, str] = {
    RacePhase.ROUND_1: "M1",
    RacePhase.ROUND_2: "M2",
    RacePhase.ROUND_3: "M3",
    RacePhase.MAIN: "1F",
}


class MatchConfidence(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


# Only these confidences are trusted enough to ever put a time on air.
DISPLAYABLE_CONFIDENCE = {MatchConfidence.EXACT, MatchConfidence.STRONG}


class BbsRiderLike(Protocol):
    bike_number: str | int | None
    first_name: str
    last_name: str


def _normalize(value: object) -> str:
    """casefold, strip punctuation and whitespace -- for name/plate matching."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


@dataclass(frozen=True)
class SqorzCompetitor:
    class_code: str | None
    class_name: str | None
    plate: str | None
    first_name: str | None
    last_name: str | None
    transponder: str | None
    times_by_phase: dict[str, SqorzRiderTime] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return name or (self.plate or "unknown")


def group_by_competitor(rows: list[SqorzRiderTime]) -> list[SqorzCompetitor]:
    """Collapse one-row-per-phase into one competitor with all its phases."""
    grouped: dict[tuple[str, str, str, str], SqorzCompetitor] = {}
    for row in rows:
        key = (
            _normalize(row.plate),
            _normalize(row.first_name),
            _normalize(row.last_name),
            _normalize(row.class_name),
        )
        competitor = grouped.get(key)
        if competitor is None:
            competitor = SqorzCompetitor(
                class_code=row.class_code,
                class_name=row.class_name,
                plate=row.plate,
                first_name=row.first_name,
                last_name=row.last_name,
                transponder=row.transponder,
            )
            grouped[key] = competitor
        competitor.times_by_phase[row.phase_code] = row
    return list(grouped.values())


@dataclass(frozen=True)
class RiderMatch:
    confidence: MatchConfidence
    competitor: SqorzCompetitor | None


@dataclass(frozen=True)
class MatchReport:
    """On-site diagnosability: what matched, what didn't, and how classes resolved."""

    counts: dict[str, int]
    unmatched_bbs: list[str]
    unmatched_sqorz: list[str]
    class_match_path: str  # "class_name" | "plate_only" | "no_sqorz_data"
    ambiguous_plates: list[str] = field(default_factory=list)


def _competitor_key(competitor: SqorzCompetitor) -> tuple[str, str, str, str]:
    return (
        _normalize(competitor.plate),
        _normalize(competitor.first_name),
        _normalize(competitor.last_name),
        _normalize(competitor.class_name),
    )


def _competitors_for_class(
    competitors: list[SqorzCompetitor],
    bbs_class_name: str,
    class_alias: str | None = None,
) -> tuple[list[SqorzCompetitor], str]:
    if not competitors:
        return [], "no_sqorz_data"
    if class_alias:
        # An operator-set alias always wins over inference (see
        # SqorzClassAliasStore) -- matches against the Sqorz className or
        # classCode the operator pointed at, e.g. RaceManager "11-12 Open"
        # aliased to Sqorz's "2204".
        alias_target = _normalize(class_alias)
        aliased = [
            c
            for c in competitors
            if _normalize(c.class_name) == alias_target or _normalize(c.class_code) == alias_target
        ]
        if aliased:
            return aliased, "alias"
    target = _normalize(bbs_class_name)
    same_class = [c for c in competitors if _normalize(c.class_name) == target]
    if same_class:
        return same_class, "class_name"
    # Class names didn't line up (e.g. RaceManager "11-12 Open" vs a Sqorz
    # class code) -- fall back to plate matching across the whole event.
    return competitors, "plate_only"


def _ambiguous_sqorz_plates(competitors: list[SqorzCompetitor]) -> dict[str, list[SqorzCompetitor]]:
    """Normalised plate -> competitors sharing it, for plates that collide."""
    by_plate: dict[str, list[SqorzCompetitor]] = defaultdict(list)
    for competitor in competitors:
        normalized = _normalize(competitor.plate)
        if normalized:
            by_plate[normalized].append(competitor)
    return {plate: group for plate, group in by_plate.items() if len(group) > 1}


def _ambiguous_bbs_plates(bbs_riders: list[BbsRiderLike]) -> dict[str, list[BbsRiderLike]]:
    """Normalised bike_number -> riders sharing it, for numbers that collide."""
    by_plate: dict[str, list[BbsRiderLike]] = defaultdict(list)
    for rider in bbs_riders:
        normalized = _normalize(rider.bike_number)
        if normalized:
            by_plate[normalized].append(rider)
    return {plate: group for plate, group in by_plate.items() if len(group) > 1}


def match_class(
    bbs_riders: list[BbsRiderLike],
    bbs_class_name: str,
    sqorz_rows: list[SqorzRiderTime],
    class_alias: str | None = None,
) -> tuple[list[RiderMatch], MatchReport]:
    """Match every rider in one BBS lineup to a Sqorz competitor.

    ``class_alias``, when given, is an operator-set override (see
    SqorzClassAliasStore) pointing at the Sqorz className/classCode to use
    for this BBS class, taking priority over normalised-name matching.

    Returns matches in the same order as ``bbs_riders``, plus a report for
    on-site debugging (counts by confidence, and the unmatched names on both
    sides).
    """
    all_competitors = group_by_competitor(sqorz_rows)
    class_competitors, class_match_path = _competitors_for_class(
        all_competitors, bbs_class_name, class_alias
    )
    sqorz_ambiguous = _ambiguous_sqorz_plates(class_competitors)
    bbs_ambiguous = _ambiguous_bbs_plates(bbs_riders)

    ambiguous_plate_notes: list[str] = [
        f"{bbs_class_name} #{group[0].plate} (Sqorz): "
        + ", ".join(competitor.display_name for competitor in group)
        for group in sqorz_ambiguous.values()
    ] + [
        f"{bbs_class_name} #{group[0].bike_number} (RaceManager): "
        + ", ".join(f"{rider.first_name} {rider.last_name}".strip() for rider in group)
        for group in bbs_ambiguous.values()
    ]

    matches: list[RiderMatch] = []
    matched_keys: set[tuple[str, str, str, str]] = set()
    counts = {confidence.value: 0 for confidence in MatchConfidence}
    unmatched_bbs: list[str] = []

    for rider in bbs_riders:
        plate = _normalize(rider.bike_number)
        last = _normalize(rider.last_name)
        first_initial = _normalize(rider.first_name)[:1]

        competitor = None
        confidence = MatchConfidence.NONE

        if plate and last:
            for candidate in all_competitors:
                if _normalize(candidate.plate) == plate and _normalize(candidate.last_name) == last:
                    competitor, confidence = candidate, MatchConfidence.EXACT
                    break

        # A bare plate match ("strong") is only safe when the plate is
        # unique on BOTH sides within the resolved class -- a handful of
        # riders, where a genuine collision is implausible. Plate is not a
        # unique key on either side: USA BMX district plates collide within
        # one class (confirmed live), and nothing stops two RaceManager
        # riders in a class from sharing a bike number either. An ambiguous
        # plate can still reach "exact" above (last name disambiguates) but
        # never "strong" on plate alone -- falls through to "weak" below.
        if (
            competitor is None
            and plate
            and plate not in sqorz_ambiguous
            and plate not in bbs_ambiguous
        ):
            for candidate in class_competitors:
                if _normalize(candidate.plate) == plate:
                    # A bare plate match is also only safe when
                    # class_competitors is genuinely scoped to this rider's
                    # class -- true for "class_name" (names lined up) and
                    # "alias" (an operator explicitly confirmed the mapping,
                    # at least as trustworthy as an automatic name match).
                    # When class names didn't line up and this fell back to
                    # searching the whole event (class_match_path ==
                    # "plate_only"), that pool can be hundreds of riders
                    # across every class, and a bare plate number WILL
                    # collide by chance (confirmed against a real 829-rider
                    # national field). Never promote that to a displayed
                    # time -- cap it at "weak".
                    confidence = (
                        MatchConfidence.STRONG
                        if class_match_path in ("class_name", "alias")
                        else MatchConfidence.WEAK
                    )
                    competitor = candidate
                    break

        if competitor is None and last and first_initial:
            for candidate in class_competitors:
                if (
                    _normalize(candidate.last_name) == last
                    and _normalize(candidate.first_name)[:1] == first_initial
                ):
                    competitor, confidence = candidate, MatchConfidence.WEAK
                    break

        matches.append(RiderMatch(confidence=confidence, competitor=competitor))
        counts[confidence.value] += 1
        if competitor is not None:
            matched_keys.add(_competitor_key(competitor))
        else:
            name = f"{rider.first_name} {rider.last_name}".strip()
            unmatched_bbs.append(name)

    unmatched_sqorz = [
        competitor.display_name
        for competitor in class_competitors
        if _competitor_key(competitor) not in matched_keys
    ]

    report = MatchReport(
        counts=counts,
        unmatched_bbs=unmatched_bbs,
        unmatched_sqorz=unmatched_sqorz,
        class_match_path=class_match_path,
        ambiguous_plates=ambiguous_plate_notes,
    )
    return matches, report


def time_for_phase(match: RiderMatch, phase_code: str) -> float | None:
    """A displayable time for this match at this phase, or None.

    Returns None whenever the match confidence isn't "exact"/"strong", the
    phase has no recorded time, or the rider has no result for this phase at
    all -- never a guess.
    """
    if match.confidence not in DISPLAYABLE_CONFIDENCE or match.competitor is None:
        return None
    row = match.competitor.times_by_phase.get(phase_code)
    return row.time_seconds if row else None
