"""WebSocket broadcast feed that emits only changed snapshots."""
import asyncio
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from connector.dependencies import get_current_lineup_service, get_current_moto_service
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService

router=APIRouter(tags=['broadcast websocket'])

@router.websocket('/ws/broadcast')
async def broadcast_socket(websocket:WebSocket,demo:bool=False,current:CurrentMotoService=Depends(get_current_moto_service),lineups:CurrentLineupService=Depends(get_current_lineup_service)):
    await websocket.accept()
    previous=''
    try:
        while True:
            state=current.get()
            try:
                lineup=lineups.get(demo=demo)
            except Exception:
                lineup=None
            payload={'type':'snapshot','current':state.model_dump(mode='json'),'lineup':lineup.model_dump(mode='json') if lineup else None}
            encoded=json.dumps(payload,sort_keys=True)
            if encoded!=previous:
                await websocket.send_json(payload)
                previous=encoded
            await asyncio.sleep(.25)
    except WebSocketDisconnect:
        return
