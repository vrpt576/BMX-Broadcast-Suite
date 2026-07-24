from datetime import datetime
from uuid import uuid4

from connector.models import MotoState
from connector.services.motoboard_service import MotoboardService


class FakeDatabase:
    def __init__(self, rows):
        self.rows = rows

    def fetch_all(self, query, params=None):
        return self.rows


def rider_row(moto_number: int, rider_order: int, finish_1=None):
    now = datetime(2026, 7, 23, 18, 31, rider_order)
    return {
        "moto_number": moto_number,
        "motogroup_number": 1,
        "class_id": uuid4(),
        "class_name": "7 Intermediate",
        "class_name_short": "7 Inter",
        "round_id": uuid4(),
        "round_type_id": 123,
        "motogroup_rider_id": uuid4(),
        "rider_order": rider_order,
        "lane_1": rider_order * 2,
        "lane_2": None,
        "lane_3": None,
        "finish_1": finish_1,
        "finish_2": None,
        "finish_3": None,
        "did_not_race": False,
        "updated_at": now,
        "rider_id": uuid4(),
        "bike_number": rider_order,
        "first_name": "Rider",
        "last_name": str(rider_order),
        "nickname": None,
        "proficiency": "I",
        "sponsor": None,
    }


def test_groups_riders_and_marks_staged():
    rows = [rider_row(1, 1), rider_row(1, 2)]
    result = MotoboardService(FakeDatabase(rows)).list_motos(uuid4())
    assert result.count == 1
    assert result.motos[0].state == MotoState.STAGED
    assert result.motos[0].riders_total == 2


def test_marks_partially_scored_moto():
    rows = [rider_row(1, 1, 1), rider_row(1, 2)]
    moto = MotoboardService(FakeDatabase(rows)).list_motos(uuid4()).motos[0]
    assert moto.state == MotoState.SCORING
    assert moto.riders_scored == 1


def test_marks_fully_scored_moto():
    rows = [rider_row(1, 1, 1), rider_row(1, 2, 2)]
    moto = MotoboardService(FakeDatabase(rows)).list_motos(uuid4()).motos[0]
    assert moto.state == MotoState.SCORED
    assert moto.riders_scored == moto.riders_total == 2
    assert moto.updated_at == rows[-1]["updated_at"]
