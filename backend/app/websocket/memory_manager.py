"""
WebSocket manager for standalone mode (без Redis pubsub).

Reads from asyncio.Queue provided by InMemoryProgressReporter.
"""

import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("video_processor.websocket.memory")


class InMemoryConnectionManager:
    """
    WebSocket manager that reads from InMemoryProgressReporter queues.

    Replaces the Redis pubsub listener from websocket/manager.py.
    """

    def __init__(self, progress_reporter):
        """
        Args:
            progress_reporter: InMemoryProgressReporter instance
        """
        self._progress = progress_reporter
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """Accepts WebSocket connection and tracks it."""
        await websocket.accept()
        self._connections.setdefault(task_id, []).append(websocket)
        logger.info(f"WebSocket connected for task {task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Removes WebSocket from tracking."""
        if task_id in self._connections:
            self._connections[task_id] = [
                ws for ws in self._connections[task_id] if ws != websocket
            ]
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info(f"WebSocket disconnected for task {task_id}")

    async def listen_and_forward(self, task_id: str, websocket: WebSocket):
        """
        Listens to progress updates and forwards to WebSocket.

        Same signature as ConnectionManager.listen_and_forward() from websocket/manager.py.

        This method:
        1. Subscribes to task progress via InMemoryProgressReporter
        2. Waits for messages on the asyncio.Queue
        3. Forwards messages to WebSocket client
        4. Stops on task completion or disconnect
        """
        queue = self._progress.subscribe(task_id)

        try:
            while True:
                # Wait for next progress update
                message = await queue.get()

                try:
                    # Send to WebSocket client
                    await websocket.send_text(message)

                    # Check if task is completed or failed
                    try:
                        parsed = json.loads(message)
                        state = parsed.get("state", "")
                        if state in ("completed", "failed"):
                            logger.info(
                                f"Task {task_id} reached terminal state: {state}"
                            )
                            break
                    except json.JSONDecodeError:
                        pass

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected by client for task {task_id}")
                    break

                except Exception as e:
                    logger.error(f"Error sending WebSocket message: {e}")
                    break

        finally:
            # Cleanup subscription
            self._progress.unsubscribe(task_id, queue)
            self.disconnect(task_id, websocket)
