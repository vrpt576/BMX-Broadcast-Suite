from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from connector.dependencies import get_event_service, get_motoboard_service
from connector.models import Moto, MotoList
from connector.services.event_service import EventNotFoundError, EventService
from connector.services.motoboard_service import MotoNotFoundError, MotoboardService

router = APIRouter(prefix="/motos", tags=["motos"])


def resolve_motoboard(
    motoboard_id: UUID | None,
    events: EventService,
) -> UUID:
    if motoboard_id is not None:
        return motoboard_id
    return events.current().motoboard_id


@router.get("", response_model=MotoList)
def list_motos(
    motoboard_id: UUID | None = Query(
        default=None,
        description="Defaults to the newest event's motoboard.",
    ),
    events: EventService = Depends(get_event_service),
    motos: MotoboardService = Depends(get_motoboard_service),
) -> MotoList:
    try:
        return motos.list_motos(resolve_motoboard(motoboard_id, events))
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{moto_number}", response_model=Moto)
def get_moto(
    moto_number: int,
    motoboard_id: UUID | None = Query(default=None),
    events: EventService = Depends(get_event_service),
    motos: MotoboardService = Depends(get_motoboard_service),
) -> Moto:
    try:
        return motos.get_moto(resolve_motoboard(motoboard_id, events), moto_number)
    except (EventNotFoundError, MotoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
