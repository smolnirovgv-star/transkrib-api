"""
In-memory progress reporter for standalone mode (без Redis).

Thread-safe замена ProgressReporter из workers/progress.py.
Сохраняет данные в dict вместо Redis, использует asyncio.Queue для WebSocket.
"""

import json
import os
import asyncio
import logging
from datetime import datetime, timezone
from threading import Lock
from collections import deque
from typing import Optional

from ..models.enums import TaskState

logger = logging.getLogger("video_processor.memory_progress")


class InMemoryProgressReporter:
    """
    Thread-safe in-memory replacement for Redis-based ProgressReporter.

    Features:
    - Stores task data in Python dict (не требует Redis)
    - Thread-safe via threading.Lock
    - WebSocket support via asyncio.Queue
    - Same interface as ProgressReporter for drop-in replacement
    """

    def __init__(self):
        self._tasks: dict[str, dict] = {}  # task_id -> task data
        self._task_order: deque = deque(maxlen=200)  # Recent tasks, LIFO
        self._lock = Lock()  # Thread safety for dict access
        self._subscribers: dict[str, list[asyncio.Queue]] = {}  # task_id -> [Queue]
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # Event loop reference
        from ..config import settings
        self._tasks_file = settings.storage_dir / 'tasks.json'
        self._load_tasks()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop for WebSocket notifications."""
        self._loop = loop

    def report(
        self,
        task_id: str,
        state: TaskState,
        progress: float,
        message: str,
        result_filename: str | None = None,
        error_message: str | None = None,
    ):
        """
        Updates task progress.

        Same signature as ProgressReporter.report() from workers/progress.py.
        Thread-safe — can be called from worker thread.
        """
        now = datetime.now(timezone.utc).isoformat()

        update = {
            "task_id": task_id,
            "state": state.value,
            "current_step": state.value,
            "progress_percent": progress,  # Store as float (Redis version stores as string)
            "step_details": message,
            "result_filename": result_filename or "",
            "error_message": error_message or "",
            "updated_at": now,
        }

        # Update dict (thread-safe)
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(update)
            else:
                # Task not initialized yet — create it with required fields
                self._tasks[task_id] = {**update, "created_at": now, "source_type": "", "source_name": ""}

        # Push to WebSocket subscribers (cross-thread asyncio communication)
        ws_msg = {
            "task_id": task_id,
            "state": state.value,
            "step": state.value,
            "progress": progress,
            "message": message,
            "error_message": error_message or "",
            "timestamp": now,
        }
        self._notify_subscribers(task_id, json.dumps(ws_msg))
        self._save_tasks()

        logger.debug(
            f"Progress [{task_id}]: {state.value} {progress:.0f}% - {message}"
        )

    def create_task(self, task_id: str, source_type: str, source_name: str):
        """
        Initializes task metadata.

        Same signature as ProgressReporter.create_task().
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "state": TaskState.PENDING.value,
                "source_type": source_type,
                "source_name": source_name,
                "current_step": "",
                "progress_percent": 0.0,
                "step_details": "",
                "result_filename": "",
                "error_message": "",
                "created_at": now,
                "updated_at": now,
            }

            # Track in order (most recent first)
            if task_id in self._task_order:
                self._task_order.remove(task_id)
            self._task_order.appendleft(task_id)

        self._save_tasks()

    def get_task(self, task_id: str) -> dict | None:
        """
        Gets task status.

        Same signature as ProgressReporter.get_task().
        Returns None if task not found.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                # Ensure progress_percent is float (for compatibility with REST endpoints)
                task["progress_percent"] = float(task.get("progress_percent", 0))
                return task.copy()
            return None

    def list_tasks(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """
        Lists recent tasks.

        Same signature as ProgressReporter.list_tasks().
        """
        with self._lock:
            # Get task IDs in order
            task_ids = list(self._task_order)[offset : offset + limit]
            tasks = []
            for tid in task_ids:
                if tid in self._tasks:
                    task = self._tasks[tid].copy()
                    task["progress_percent"] = float(task.get("progress_percent", 0))
                    tasks.append(task)
            return tasks

    # Persistence methods

    def _save_tasks(self):
        """Persist tasks to JSON file."""
        try:
            with self._lock:
                data = {tid: dict(t) for tid, t in self._tasks.items()}
                order = list(self._task_order)
            payload = {'tasks': data, 'order': order}
            tmp_path = str(self._tasks_file) + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self._tasks_file))
        except Exception as e:
            logger.warning('Failed to save tasks: ' + str(e))

    def _load_tasks(self):
        """Load tasks from JSON file on startup."""
        try:
            if not self._tasks_file.exists():
                return
            with open(str(self._tasks_file), 'r', encoding='utf-8') as f:
                payload = json.load(f)
            tasks = payload.get('tasks', {})
            order = payload.get('order', [])
            with self._lock:
                self._tasks.update(tasks)
                for tid in reversed(order):
                    if tid not in self._task_order:
                        self._task_order.appendleft(tid)
            logger.info('Loaded ' + str(len(tasks)) + ' tasks from ' + str(self._tasks_file))
        except Exception as e:
            logger.warning('Failed to load tasks: ' + str(e))

    # WebSocket subscription methods

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """
        WebSocket manager calls this to get a queue for a task.

        Returns:
            asyncio.Queue that will receive progress updates
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=100)

        with self._lock:
            self._subscribers.setdefault(task_id, []).append(q)

        logger.debug(f"WebSocket subscribed to task {task_id}")
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue):
        """Removes a subscriber queue."""
        with self._lock:
            if task_id in self._subscribers:
                self._subscribers[task_id] = [
                    sub for sub in self._subscribers[task_id] if sub is not q
                ]
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

        logger.debug(f"WebSocket unsubscribed from task {task_id}")

    def _notify_subscribers(self, task_id: str, message: str):
        """
        Pushes message to all WebSocket subscribers (cross-thread).

        Called from worker thread, must safely communicate with asyncio event loop.
        """
        with self._lock:
            queues = self._subscribers.get(task_id, [])[:]

        if not queues:
            return

        # Thread-safe way to put into asyncio queue from non-async thread
        for q in queues:
            try:
                if self._loop and not self._loop.is_closed():
                    # Schedule put_nowait from the worker thread
                    self._loop.call_soon_threadsafe(self._put_nowait, q, message)
                else:
                    # Fallback if loop not set
                    try:
                        q.put_nowait(message)
                    except asyncio.QueueFull:
                        logger.warning(f"WebSocket queue full for task {task_id}")
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

    @staticmethod
    def _put_nowait(q: asyncio.Queue, item: str):
        """Helper to put item into queue (called via call_soon_threadsafe)."""
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass  # Drop message if queue is full (slow consumer)
