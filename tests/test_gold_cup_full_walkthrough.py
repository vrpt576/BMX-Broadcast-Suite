"""Step through every moto of every round of the historic 2026-08-01 Gold Cup.

The other Gold Cup regression module only covers the four-moto Main window
that was originally exported.  This module walks the *whole* 65-moto program
-- every phase RaceManager actually produced, every displayed slot in it,
forwards and backwards -- and asserts what the operator sees on the Race
Director, the controller and the OBS overlays.
"""

from __future__ import annotations

import inspect
import re
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID

import pytest

from connector.models import CurrentMoto, CurrentMotoUpdate, RacePhase
from connector.routes import current as current_routes
from connector.routes import director, lineup
from connector.services.race_program_service import (
    RaceSlotUnavailableError,
)
from connector.services.race_slot_service import RaceSlotService
from tests.gold_cup_full_program import (
    OPERATOR_MAIN_PROGRAM_START,
    fixture,
    full_program_rows,
    services,
)

# Labels BBS is allowed to put on air.  "Round 3" is deliberately absent:
# v1.2.16 retired it, and RaceManager never produces it either -- a third
# qualifying moto is "Moto 3", and only a class that ends on that moto is
# announced as its "Main".
DISPLAYABLE_LABELS = {"Round 1", "Round 2", "Moto 3", "Main", "Qtr", "Semi", "LCQ"}

BANNED_LABEL = "Round 3"

_PHASE_LABEL_MAP = re.compile(
    r"phaseLabels\s*=\s*\{(?P<body>[^}]*)\}", re.MULTILINE
)
_PHASE_LABEL_ENTRY = re.compile(r"(?P<phase>\w+)\s*:\s*'(?P<label>[^']*)'")


def ui_phase_labels(module) -> list[dict[str, str]]:
    """Every phaseLabels map shipped in one of the served pages."""
    source = Path(inspect.getsourcefile(module)).read_text(encoding="utf-8")
    return [
        {
            item.group("phase"): item.group("label")
            for item in _PHASE_LABEL_ENTRY.finditer(match.group("body"))
        }
        for match in _PHASE_LABEL_MAP.finditer(source)
    ]


# The Race round menu is rendered from the Director's own map, so read the
# labels the operator sees straight out of the shipped page.
PHASE_MENU_LABELS = ui_phase_labels(director)[0]


def pin(current, board: UUID) -> None:
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=board))


def catalogs(boards, board: UUID) -> dict[RacePhase, list]:
    slots = RaceSlotService(boards)
    return {
        phase: slots.catalog(board, phase)
        for phase in RacePhase
        if slots.catalog(board, phase)
    }


def program_stage(boards, board: UUID, slot, member) -> object:
    """The stage /api/current/program reports for this displayed slot."""
    probe = CurrentMoto(
        moto_number=slot.moto_number,
        race_phase=slot.phase,
        motoboard_id=board,
        class_id=member.stage.class_id,
        round_type_id=member.stage.round_type_id,
        round_id=member.stage.round_id,
        motogroup_id=member.stage.motogroup_id,
        qualifier_motogroup_id=member.qualifier_motogroup_id,
    )
    program = boards.get_program(board, probe)
    return next(
        (stage for stage in program.stages if stage.phase == slot.phase),
        None,
    )


# --------------------------------------------------------------------------
# The export itself
# --------------------------------------------------------------------------


def test_fixture_holds_the_whole_event_and_no_rider_data() -> None:
    payload = fixture()

    assert payload["source"]["contains_rider_personal_data"] is False
    assert payload["source"]["total_motos"] == 65
    assert len(payload["classes"]) == 62
    assert len(payload["motogroups"]) == 127
    qualifiers = [item for item in payload["motogroups"] if item["round_type_id"] == 123]
    finals = [item for item in payload["motogroups"] if item["round_type_id"] == 1]
    assert len(qualifiers) == 65
    assert len(finals) == 62
    assert {item["moto_number"] for item in qualifiers} == set(range(1, 66))
    assert sum(len(item["riders"]) for item in payload["motogroups"]) == 600
    forbidden = {"first_name", "last_name", "nickname", "bike_number", "home_track"}
    for group in payload["motogroups"]:
        for rider in group["riders"]:
            assert not forbidden.intersection(rider)


def test_every_class_has_a_qualifier_and_a_final_record() -> None:
    rows = full_program_rows()
    branches = defaultdict(set)
    for row in rows:
        branches[row["class_id"]].add(row["round_type_id"])
    assert len(branches) == 62
    assert all(value == {1, 123} for value in branches.values())


# --------------------------------------------------------------------------
# Walking the program
# --------------------------------------------------------------------------


def test_the_event_exposes_exactly_the_phases_race_manager_produced(
    tmp_path: Path,
) -> None:
    board, boards, current, programs = services(tmp_path)
    pin(current, board)

    assert [phase.value for phase in programs.available_phases()] == [
        "round_1",
        "round_2",
        "round_3",
        "main",
    ]
    available = catalogs(boards, board)
    assert [slot.moto_number for slot in available[RacePhase.ROUND_1]] == list(range(1, 66))
    assert [slot.moto_number for slot in available[RacePhase.ROUND_2]] == list(range(1, 66))
    assert [slot.moto_number for slot in available[RacePhase.MAIN]] == list(range(28, 63))


@pytest.mark.parametrize(
    "phase",
    [RacePhase.ROUND_1, RacePhase.ROUND_2, RacePhase.ROUND_3, RacePhase.MAIN],
)
def test_stepping_visits_every_moto_in_the_round_exactly_once(
    tmp_path: Path,
    phase: RacePhase,
) -> None:
    board, boards, current, programs = services(tmp_path)
    pin(current, board)
    expected = [slot.moto_number for slot in RaceSlotService(boards).catalog(board, phase)]

    programs.select_moto(
        CurrentMotoUpdate(moto_number=expected[0], race_phase=phase, motoboard_id=board)
    )
    walked = [current.get().moto_number]
    for _ in range(len(expected) - 1):
        walked.append(programs.step_moto(1).moto_number)

    assert walked == expected
    assert Counter(walked).most_common(1)[0][1] == 1
    assert programs.step_moto(1).moto_number == expected[-1], (
        "Stepping past the last moto of a round must hold position"
    )

    back = [programs.step_moto(-1).moto_number for _ in range(len(expected) - 1)]
    assert back == list(reversed(expected[:-1]))
    assert programs.step_moto(-1).moto_number == expected[0], (
        "Stepping before the first moto of a round must hold position"
    )
    assert current.get().race_phase == phase


@pytest.mark.parametrize(
    "phase",
    [RacePhase.ROUND_1, RacePhase.ROUND_2, RacePhase.ROUND_3, RacePhase.MAIN],
)
def test_every_moto_in_the_round_can_be_jumped_to_directly(
    tmp_path: Path,
    phase: RacePhase,
) -> None:
    board, boards, current, programs = services(tmp_path)
    pin(current, board)
    slots = RaceSlotService(boards).catalog(board, phase)

    for slot in slots:
        state = programs.select_moto(
            CurrentMotoUpdate(
                moto_number=slot.moto_number,
                race_phase=phase,
                motoboard_id=board,
            )
        )
        assert state.moto_number == slot.moto_number
        assert state.race_phase == phase
        assert state.class_name == slot.class_name
        assert state.phase_label == slot.phase_label


def test_jumping_to_a_moto_the_round_does_not_contain_is_refused(
    tmp_path: Path,
) -> None:
    board, _boards, current, programs = services(tmp_path)
    pin(current, board)

    with pytest.raises(RaceSlotUnavailableError) as error:
        programs.select_moto(
            CurrentMotoUpdate(moto_number=1, race_phase=RacePhase.MAIN, motoboard_id=board)
        )
    assert error.value.previous_moto is None
    assert error.value.next_moto == 28


def test_first_and_last_moto_shortcuts_land_on_the_round_boundaries(
    tmp_path: Path,
) -> None:
    board, boards, current, programs = services(tmp_path)
    pin(current, board)
    for phase in (RacePhase.ROUND_1, RacePhase.ROUND_2, RacePhase.ROUND_3, RacePhase.MAIN):
        slots = RaceSlotService(boards).catalog(board, phase)
        programs.select_moto(
            CurrentMotoUpdate(
                moto_number=slots[len(slots) // 2].moto_number,
                race_phase=phase,
                motoboard_id=board,
            )
        )
        assert programs.select_phase_boundary(last=False).moto_number == slots[0].moto_number
        assert programs.select_phase_boundary(last=True).moto_number == slots[-1].moto_number


def test_stepping_rounds_keeps_the_class_and_never_leaves_the_program(
    tmp_path: Path,
) -> None:
    board, _boards, current, programs = services(tmp_path)
    pin(current, board)
    programs.select_moto(
        CurrentMotoUpdate(moto_number=39, race_phase=RacePhase.ROUND_1, motoboard_id=board)
    )
    opening = current.get().class_name

    second = programs.step_phase(1)
    assert second.race_phase == RacePhase.ROUND_2
    assert second.class_name == opening

    third = programs.step_phase(1)
    assert third.race_phase == RacePhase.ROUND_3
    assert third.class_name == opening

    main = programs.step_phase(1)
    assert main.race_phase == RacePhase.MAIN
    assert main.class_name == opening

    assert programs.step_phase(1).race_phase == RacePhase.MAIN
    assert programs.step_phase(-1).race_phase == RacePhase.ROUND_3


# --------------------------------------------------------------------------
# What the operator actually reads on screen
# --------------------------------------------------------------------------


def test_no_displayed_round_label_is_round_3(tmp_path: Path) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    offenders: list[str] = []

    for phase, slots in catalogs(boards, board).items():
        for slot in slots:
            if slot.phase_label == BANNED_LABEL:
                offenders.append(f"slot {phase.value} moto {slot.moto_number} {slot.class_name}")
            stage = program_stage(boards, board, slot, slot.members[0])
            if stage is not None and stage.label == BANNED_LABEL:
                offenders.append(
                    f"program {phase.value} moto {slot.moto_number} {slot.class_name}"
                )

    assert offenders == [], (
        f'"{BANNED_LABEL}" is still displayed for {len(offenders)} stages, '
        f"first: {offenders[:3]}"
    )


def test_every_displayed_label_is_one_bbs_is_allowed_to_show(tmp_path: Path) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    labels = {
        slot.phase_label for slots in catalogs(boards, board).values() for slot in slots
    }
    assert labels <= DISPLAYABLE_LABELS, f"unexpected labels: {labels - DISPLAYABLE_LABELS}"


def test_the_slot_label_and_the_program_label_agree(tmp_path: Path) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    disagreements: list[str] = []

    for phase, slots in catalogs(boards, board).items():
        for slot in slots:
            stage = program_stage(boards, board, slot, slot.members[0])
            assert stage is not None, f"{phase.value} moto {slot.moto_number} has no stage"
            if stage.label != slot.phase_label:
                disagreements.append(
                    f"{phase.value} moto {slot.moto_number} {slot.class_name}: "
                    f"navigation shows {slot.phase_label!r}, "
                    f"/api/current/program returns {stage.label!r}"
                )

    assert disagreements == [], "\n".join(disagreements)


def test_the_qualifying_rounds_and_the_main_each_show_one_label(
    tmp_path: Path,
) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    available = catalogs(boards, board)
    for phase, expected in (
        (RacePhase.ROUND_1, "Round 1"),
        (RacePhase.ROUND_2, "Round 2"),
        (RacePhase.MAIN, "Main"),
    ):
        labels = {slot.phase_label for slot in available[phase]}
        assert labels == {expected}, f"{phase.value} shows {sorted(labels)}"


def test_a_third_moto_is_only_called_main_when_the_class_ends_there(
    tmp_path: Path,
) -> None:
    """The third round legitimately holds two kinds of slot.

    A Total Points class has no separately raced final, so its third moto is
    its Main.  A class that still races a Main is running a qualifier, and is
    labelled "Moto 3" -- never "Round 3", and never "Main".
    """
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    available = catalogs(boards, board)
    classes_with_a_main = {
        class_id
        for slot in available[RacePhase.MAIN]
        for class_id in slot.class_ids
    }

    wrong: list[str] = []
    for slot in available[RacePhase.ROUND_3]:
        still_to_race = bool(classes_with_a_main.intersection(slot.class_ids))
        expected = "Moto 3" if still_to_race else "Main"
        if slot.phase_label != expected:
            wrong.append(
                f"moto {slot.moto_number} {slot.class_name}: "
                f"expected {expected!r}, shows {slot.phase_label!r}"
            )
    assert wrong == [], "\n".join(wrong)

    seen = Counter(slot.phase_label for slot in available[RacePhase.ROUND_3])
    assert seen == {"Main": 27, "Moto 3": 9}


def test_the_race_round_menu_never_offers_two_identical_entries(
    tmp_path: Path,
) -> None:
    """The menu label comes from the UI's own phase map, not from a slot."""
    board, boards, current, programs = services(tmp_path)
    pin(current, board)
    offered = [PHASE_MENU_LABELS[phase.value] for phase in programs.available_phases()]

    duplicates = [label for label, count in Counter(offered).items() if count > 1]
    assert duplicates == [], f"the Race round menu shows {duplicates} twice: {offered}"
    assert BANNED_LABEL not in offered


def test_a_class_is_only_ever_announced_as_main_once(tmp_path: Path) -> None:
    """A class has one final.  It must not appear as "Main" at two motos."""
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    mains: dict[UUID, list[str]] = defaultdict(list)

    for phase, slots in catalogs(boards, board).items():
        for slot in slots:
            if slot.phase_label != "Main":
                continue
            for class_id in slot.class_ids:
                mains[class_id].append(f"{phase.value} moto {slot.moto_number}")

    repeated = {
        slot: where for slot, where in mains.items() if len(where) > 1
    }
    assert repeated == {}, (
        f"{len(repeated)} classes are shown as Main twice, e.g. "
        f"{list(repeated.values())[:3]}"
    )


def test_a_qualifying_moto_is_never_labelled_main(tmp_path: Path) -> None:
    """Round 1/2/3 slots for a class that still has a Main to race."""
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    available = catalogs(boards, board)
    classes_with_a_main = {
        class_id
        for slot in available.get(RacePhase.MAIN, [])
        for class_id in slot.class_ids
    }
    offenders: list[str] = []

    for phase in (RacePhase.ROUND_1, RacePhase.ROUND_2, RacePhase.ROUND_3):
        for slot in available.get(phase, []):
            if slot.phase_label != "Main":
                continue
            if classes_with_a_main.intersection(slot.class_ids):
                offenders.append(f"{phase.value} moto {slot.moto_number} {slot.class_name}")

    assert offenders == [], (
        "qualifying motos announced as Main while the class still races a Main: "
        f"{offenders}"
    )


def test_the_total_points_third_moto_is_announced_as_main(tmp_path: Path) -> None:
    """v1.2.16's fix: a 3-moto Total Points class ends on its third moto."""
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    labels = {
        (phase, slot.moto_number): slot.phase_label
        for phase, slots in catalogs(boards, board).items()
        for slot in slots
    }
    # 5 & Under Intermediate: three scored motos, no separate final race.
    assert labels[(RacePhase.MAIN, 29)] == "Main"
    assert (RacePhase.ROUND_3, 29) not in labels


def test_the_main_program_matches_the_operator_confirmed_boundary(
    tmp_path: Path,
) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    boundary = boards.get_main_program_boundary(board)
    mains = RaceSlotService(boards).catalog(board, RacePhase.MAIN)

    assert boundary.start_moto == OPERATOR_MAIN_PROGRAM_START
    assert boundary.suggested_start_moto == OPERATOR_MAIN_PROGRAM_START
    assert min(slot.moto_number for slot in mains) == OPERATOR_MAIN_PROGRAM_START
    assert [slot.moto_number for slot in mains] == list(range(28, 63))
    assert all(not slot.combined for slot in mains)
    assert len({slot.class_name for slot in mains}) == len(mains)


def test_round_one_runs_the_published_running_order(tmp_path: Path) -> None:
    board, boards, current, _programs = services(tmp_path)
    pin(current, board)
    order = [
        (slot.moto_number, slot.class_name)
        for slot in RaceSlotService(boards).catalog(board, RacePhase.ROUND_1)
    ]
    assert order[:5] == [
        (1, "4 Balance Bike"),
        (2, "3 Balance Bike"),
        (3, "1-2 Balance Bike"),
        (4, "8 & Under Girls Cruiser"),
        (5, "11-12 Girls Cruiser"),
    ]
    assert order[-3:] == [
        (63, "17-20 Expert"),
        (64, "26-35 Expert"),
        (65, "46-50 Expert"),
    ]
    assert len({name for _, name in order}) == 62


# --------------------------------------------------------------------------
# The Main program boundary the operator types in
# --------------------------------------------------------------------------


def test_boundary_left_unresolved_still_walks_the_whole_program(
    tmp_path: Path,
) -> None:
    board, boards, current, programs = services(tmp_path, main_program_start=None)
    pin(current, board)
    boundary = boards.get_main_program_boundary(board)

    assert boundary.start_moto is None
    assert boundary.suggested_start_moto == OPERATOR_MAIN_PROGRAM_START
    assert boundary.confidence.value == "low"
    # Transfer finals are still navigable; only the Total Points classes move.
    mains = RaceSlotService(boards).catalog(board, RacePhase.MAIN)
    assert [slot.moto_number for slot in mains] == [
        item for item in range(28, 63) if item not in {29, 30}
    ]


def test_setting_the_boundary_to_moto_one_pulls_every_class_into_the_main(
    tmp_path: Path,
) -> None:
    """Guard for the live setting seen on the Race Director (start = 1).

    Moto 1 is not this event's Main block; typing it makes every Total Points
    class's accumulated classification appear as a Main race, and shrinks the
    third-round walk to the nine classes that really do run a separate final.
    """
    board, boards, current, _programs = services(tmp_path, main_program_start=1)
    pin(current, board)
    available = catalogs(boards, board)

    mains = available[RacePhase.MAIN]
    assert len(mains) == 62, "every class, not just the 35 Main-program classes"
    assert mains[0].moto_number == 1
    assert len(available[RacePhase.ROUND_3]) == 9


def test_every_served_page_uses_the_same_round_wording() -> None:
    """Director, controller and both overlays must agree, and drop Round 3."""
    maps = (
        ui_phase_labels(director)
        + ui_phase_labels(current_routes)
        + ui_phase_labels(lineup)
    )
    assert len(maps) == 4, "expected the Director, controller and two overlays"

    for labels in maps:
        assert set(labels) == {
            "round_1",
            "round_2",
            "round_3",
            "quarterfinal",
            "semifinal",
            "main",
        }
        assert BANNED_LABEL not in labels.values()
        assert labels["round_3"].upper() == "MOTO 3"
        assert labels["round_3"].upper() != labels["main"].upper()

    # Overlays shout; the Director and controller do not.
    assert {frozenset(item.items()) for item in maps}.__len__() == 2
