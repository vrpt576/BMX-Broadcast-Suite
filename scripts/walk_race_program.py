#!/usr/bin/env python3
"""Print every displayed slot of every round for the Gold Cup fixture.

A human-readable companion to tests/test_gold_cup_full_walkthrough.py: run it
to eyeball exactly what the Race Director would show while stepping through a
historic event.

    python scripts/walk_race_program.py [--main-program-start 28]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connector.models import RacePhase  # noqa: E402
from connector.services.race_slot_service import RaceSlotService  # noqa: E402
from tests.gold_cup_full_program import (  # noqa: E402
    OPERATOR_MAIN_PROGRAM_START,
    services,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--main-program-start",
        type=int,
        default=OPERATOR_MAIN_PROGRAM_START,
        help="Operator-confirmed Main program start moto (0 = leave unresolved)",
    )
    options = parser.parse_args()
    start = options.main_program_start or None

    board, boards, _current, _programs = services(
        Path(tempfile.mkdtemp()), main_program_start=start
    )
    slots = RaceSlotService(boards)
    boundary = boards.get_main_program_boundary(board)
    print(f"Main program start: {boundary.start_moto} ({boundary.source.value})")

    for phase in RacePhase:
        catalog = slots.catalog(board, phase)
        if not catalog:
            continue
        print(f"\n=== {phase.value} — {len(catalog)} motos ===")
        for slot in catalog:
            stage = slot.members[0].stage
            print(
                f"  moto {slot.moto_number:>2}  {slot.phase_label:<8}"
                f"  {slot.class_name:<26}  {stage.competition_stage.value}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
