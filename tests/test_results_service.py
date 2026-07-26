from pathlib import Path
from connector.models import CurrentMotoUpdate
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService

class Noop: pass

def test_demo_results_are_sorted_by_finish(tmp_path: Path):
    current=CurrentMotoService(tmp_path/'current.json')
    current.set(CurrentMotoUpdate(moto_number=1))
    lineups=CurrentLineupService(current,Noop(),Noop(),tmp_path/'cache.json')
    service=CurrentResultsService(current,Noop(),Noop(),lineups)
    result=service.get(demo=True)
    assert [r.finish for r in result.riders]==[1,2,3,4]
    assert result.experimental is True
