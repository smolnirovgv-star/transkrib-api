"""WebSocket connection manager with Redis pubsub bridge."""

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

logger = logging.getLogger("video_processor.websocket")


class ConnectionManager:
    """Manages WebSocket connections and bridges Redis pubsub to clients."""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(task_id, []).append(websocket)
        logger.info(f"WS connected: task={task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        if task_id in self._connections:
            self._connections[task_id] = [
                ws for ws in self._connections[task_id] if ws != websocket
            ]
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info(f"WS disconnected: task={task_id}")

    async def listen_and_forward(self, task_id: str, websocket: WebSocket):
        """
        Subscribes to Redis pubsub channel for task progress
        and forwards messages to the WebSocket client.
        """
        r = aioredis.from_url(self._redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"progress:{task_id}")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        await websocket.send_text(data)
                        # Check if task is done
                        parsed = json.loads(data)
                        if parsed.get("state") in ("completed", "failed"):
                            break
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"WS send error: {e}")
                        break
        finally:
            await pubsub.unsubscribe(f"progress:{task_id}")
            await pubsub.close()
            await r.close()
            self.disconnect(task_id, websocket)
