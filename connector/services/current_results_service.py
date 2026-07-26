"""Experimental results view derived from RaceManager finish fields."""
from connector.models import CurrentResults, ResultRider, RacePhase
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService

class CurrentResultsService:
    def __init__(self,current:CurrentMotoService,events:EventService,motos:MotoboardService,lineups:CurrentLineupService):
        self.current,self.events,self.motos,self.lineups=current,events,motos,lineups
    def get(self,*,demo:bool=False):
        state=self.current.get()
        try:
            moto=DEMO_MOTO if demo else self.motos.get_moto(self.events.current().motoboard_id,state.moto_number)
            field={RacePhase.ROUND_1:'finish_1',RacePhase.ROUND_2:'finish_2',RacePhase.ROUND_3:'finish_3'}.get(state.race_phase)
            riders=[]
            for r in moto.riders:
                finish=getattr(r,field,None) if field else next((x for x in (r.finish_3,r.finish_2,r.finish_1) if x is not None),None)
                riders.append(ResultRider(finish=finish,bike_number=r.bike_number,first_name=r.first_name,last_name=r.last_name))
            riders.sort(key=lambda r:(r.finish is None,r.finish or 999,r.last_name))
            return CurrentResults(moto_number=state.moto_number,race_phase=state.race_phase,class_name=moto.class_name or state.class_name or 'Class not set',riders=riders,source='demo' if demo else 'racemanager',updated_at=moto.updated_at)
        except Exception as exc:
            lineup=self.lineups.get(demo=False)
            return CurrentResults(moto_number=lineup.moto_number,race_phase=lineup.race_phase,class_name=lineup.class_name,riders=[],source='cache',is_stale=True,warning=str(exc))
