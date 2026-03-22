"""WebSocket endpoint for real-time task progress."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import settings
from ..websocket.manager import ConnectionManager

router = APIRouter()

manager = ConnectionManager(settings.celery_broker_url)


@router.websocket("/ws/tasks/{task_id}/progress")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    """
    WebSocket for real-time progress updates.
    Client connects, receives ProgressUpdate JSON messages until task completes.
    """
    await manager.connect(task_id, websocket)
    try:
        await manager.listen_and_forward(task_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
    except Exception:
        manager.disconnect(task_id, websocket)
