"""Progress reporter: writes task progress to Redis for REST polling and WebSocket broadcast."""

import json
import logging
from datetime import datetime, timezone

import redis

from ..models.enums import TaskState

logger = logging.getLogger("video_processor.progress")


class ProgressReporter:
    def __init__(self, redis_url: str):
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def report(self, task_id: str, state: TaskState, progress: float, message: str,
               result_filename: str | None = None, error_message: str | None = None):
        """
        Updates task progress in Redis.
        - HSET for REST polling (GET /api/tasks/{id})
        - PUBLISH for WebSocket broadcast
        """
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "task_id": task_id,
            "state": state.value,
            "current_step": state.value,
            "progress_percent": str(progress),
            "step_details": message,
            "result_filename": result_filename or "",
            "error_message": error_message or "",
            "updated_at": now,
        }

        # Hash for polling
        self._redis.hset(f"task:{task_id}", mapping=update)
        # Set expiry (24 hours)
        self._redis.expire(f"task:{task_id}", 86400)

        # Pubsub for WebSocket
        ws_msg = {
            "task_id": task_id,
            "state": state.value,
            "step": state.value,
            "progress": progress,
            "message": message,
            "timestamp": now,
        }
        self._redis.publish(f"progress:{task_id}", json.dumps(ws_msg))

        logger.debug(f"Progress [{task_id}]: {state.value} {progress:.0f}% - {message}")

    def create_task(self, task_id: str, source_type: str, source_name: str):
        """Initializes task metadata in Redis."""
        now = datetime.now(timezone.utc).isoformat()
        self._redis.hset(f"task:{task_id}", mapping={
            "task_id": task_id,
            "state": TaskState.PENDING.value,
            "source_type": source_type,
            "source_name": source_name,
            "current_step": "",
            "progress_percent": "0",
            "step_details": "",
            "result_filename": "",
            "error_message": "",
            "created_at": now,
            "updated_at": now,
        })
        self._redis.expire(f"task:{task_id}", 86400)
        # Track task in global list
        self._redis.lpush("tasks:list", task_id)
        self._redis.ltrim("tasks:list", 0, 199)  # Keep last 200

    def get_task(self, task_id: str) -> dict | None:
        """Gets task status from Redis hash."""
        data = self._redis.hgetall(f"task:{task_id}")
        if not data:
            return None
        data["progress_percent"] = float(data.get("progress_percent", 0))
        return data

    def list_tasks(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Lists recent tasks."""
        task_ids = self._redis.lrange("tasks:list", offset, offset + limit - 1)
        tasks = []
        for tid in task_ids:
            task = self.get_task(tid)
            if task:
                tasks.append(task)
        return tasks
