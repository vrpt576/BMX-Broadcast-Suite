from pathlib import Path
from connector.models import CurrentMotoUpdate
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService

class BrokenEvents:
    def current(self): raise RuntimeError('offline')
class BrokenMotos:
    pass


def test_last_known_good_is_returned_when_database_fails(tmp_path: Path):
    current=CurrentMotoService(tmp_path/'current.json')
    current.set(CurrentMotoUpdate(moto_number=1))
    service=CurrentLineupService(current,BrokenEvents(),BrokenMotos(),tmp_path/'cache.json')
    cached=service._build(current.get(),DEMO_MOTO,source='racemanager')
    service._write_cache(cached)
    result=service.get()
    assert result.source=='cache'
    assert result.is_stale is True
    assert len(result.riders)==4


def test_cache_is_not_used_for_a_different_moto(tmp_path: Path):
    current=CurrentMotoService(tmp_path/'current.json')
    current.set(CurrentMotoUpdate(moto_number=1))
    service=CurrentLineupService(current,BrokenEvents(),BrokenMotos(),tmp_path/'cache.json')
    service._write_cache(service._build(current.get(),DEMO_MOTO,source='racemanager'))
    current.set(CurrentMotoUpdate(moto_number=2))
    try:
        service.get()
    except RuntimeError:
        pass
    else:
        raise AssertionError('stale cache from another moto must not be served')
