"""
Standalone WebSocket router factory (без Redis pubsub).

Uses InMemoryConnectionManager instead of Redis-based manager.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

logger = logging.getLogger("video_processor.standalone_ws")


def create_ws_router(manager):
    """
    Factory function to create WebSocket router with injected manager.

    Args:
        manager: InMemoryConnectionManager instance

    Returns:
        APIRouter configured for WebSocket connections
    """
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/tasks/{task_id}/progress")
    async def task_progress_ws(websocket: WebSocket, task_id: str):
        """
        WebSocket endpoint for real-time task progress.

        Same path and behavior as ws.py, but uses InMemoryConnectionManager.
        """
        logger.info(f"WebSocket connection request for task {task_id}")

        await manager.connect(task_id, websocket)

        try:
            # Listen for progress updates and forward to client
            await manager.listen_and_forward(task_id, websocket)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for task {task_id}")
            manager.disconnect(task_id, websocket)

        except Exception as e:
            logger.error(f"WebSocket error for task {task_id}: {e}")
            manager.disconnect(task_id, websocket)

    return router
