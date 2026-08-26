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
"""

from __future__ import annotations

import re
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


def _competitor_key(competitor: SqorzCompetitor) -> tuple[str, str, str, str]:
    return (
        _normalize(competitor.plate),
        _normalize(competitor.first_name),
        _normalize(competitor.last_name),
        _normalize(competitor.class_name),
    )


def _competitors_for_class(
    competitors: list[SqorzCompetitor], bbs_class_name: str
) -> tuple[list[SqorzCompetitor], str]:
    if not competitors:
        return [], "no_sqorz_data"
    target = _normalize(bbs_class_name)
    same_class = [c for c in competitors if _normalize(c.class_name) == target]
    if same_class:
        return same_class, "class_name"
    # Class names didn't line up (e.g. RaceManager "11-12 Open" vs a Sqorz
    # class code) -- fall back to plate matching across the whole event.
    return competitors, "plate_only"


def match_class(
    bbs_riders: list[BbsRiderLike],
    bbs_class_name: str,
    sqorz_rows: list[SqorzRiderTime],
) -> tuple[list[RiderMatch], MatchReport]:
    """Match every rider in one BBS lineup to a Sqorz competitor.

    Returns matches in the same order as ``bbs_riders``, plus a report for
    on-site debugging (counts by confidence, and the unmatched names on both
    sides).
    """
    all_competitors = group_by_competitor(sqorz_rows)
    class_competitors, class_match_path = _competitors_for_class(all_competitors, bbs_class_name)

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

        if competitor is None and plate:
            for candidate in class_competitors:
                if _normalize(candidate.plate) == plate:
                    # A bare plate match is only safe when class_competitors
                    # is genuinely scoped to this rider's class -- a handful
                    # of riders, where a plate collision is implausible. When
                    # class names didn't line up and this fell back to
                    # searching the whole event (class_match_path ==
                    # "plate_only"), that pool can be hundreds of riders
                    # across every class, and a bare plate number WILL
                    # collide by chance (confirmed against a real 829-rider
                    # national field). Never promote that to a displayed
                    # time -- cap it at "weak".
                    confidence = (
                        MatchConfidence.STRONG
                        if class_match_path == "class_name"
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
