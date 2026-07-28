from fastapi import APIRouter, Depends, HTTPException, status

from connector.dependencies import get_event_service
from connector.models import Event
from connector.services.event_service import EventNotFoundError, EventService

router = APIRouter(prefix="/event", tags=["event"])


@router.get("/current", response_model=Event)
def current_event(service: EventService = Depends(get_event_service)) -> Event:
    try:
        return service.current()
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
