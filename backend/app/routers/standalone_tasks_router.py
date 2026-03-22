"""
Standalone tasks router (без Celery) — для desktop режима.

Запускает обработку видео в threading.Thread вместо Celery task queue.
"""

import os
import uuid
import threading
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..models.schemas import TaskResponse, TaskStatusResponse
from ..models.enums import TaskState

logger = logging.getLogger("video_processor.standalone_tasks")

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Global references — будут инъецированы из standalone_server.py
_storage = None
_progress = None
_pipeline_runner = None  # Function that runs pipeline in thread
_trial_manager = None
_license_manager = None


def set_dependencies(storage, progress, pipeline_runner, trial_manager=None, license_manager=None):
    """
    Inject dependencies (called from standalone_server.py).

    Args:
        storage: StorageService instance
        progress: InMemoryProgressReporter instance
        pipeline_runner: Function to run pipeline (from standalone_tasks.py)
        trial_manager: TrialManager instance (optional)
        license_manager: LicenseManager instance (optional)
    """
    global _storage, _progress, _pipeline_runner, _trial_manager, _license_manager
    _storage = storage
    _progress = progress
    _pipeline_runner = pipeline_runner
    _trial_manager = trial_manager
    _license_manager = license_manager


def _check_trial_gate():
    """
    Raise HTTP 403 if trial is expired/blocked/limit reached (and not licensed).
    Called at the start of upload and URL submit endpoints.
    """
    # Dev mode bypass
    if settings.dev_mode:
        logger.debug("_check_trial_gate: dev_mode=True — bypassing trial/license check")
        return
    if _trial_manager is None:
        return
    # Licensed users bypass trial limits
    if _license_manager is not None:
        is_licensed, _ = _license_manager.is_licensed()
        if is_licensed:
            return
    allowed, reason = _trial_manager.can_process()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)


class UrlSubmission(BaseModel):
    url: str
    max_duration_seconds: int | None = None
    whisper_model: str | None = None


@router.post("/upload", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    max_duration_seconds: int | None = Form(None),
    whisper_model: str | None = Form(None),
):
    """
    Upload a video file and start processing.

    Standalone version — runs in threading.Thread instead of Celery.
    """
    _check_trial_gate()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Save uploaded file
    try:
        file_path, _ = _storage.save_upload_stream(file.filename, file.file)
    except Exception as e:
        logger.error(f"Upload save error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Initialize task metadata
    _progress.create_task(task_id, source_type="file", source_name=file.filename)

    # Start processing in background thread
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, str(file_path), file.filename, max_duration_seconds, whisper_model),
        daemon=True,
    )
    thread.start()

    logger.info(f"Task {task_id} started (file: {file.filename})")

    return TaskResponse(task_id=task_id, status="pending", message="Task queued for processing")


@router.post("/url", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_url(submission: UrlSubmission):
    """
    Submit a URL (YouTube, VK, etc.) and start processing.

    Standalone version — runs in threading.Thread instead of Celery.
    """
    _check_trial_gate()

    url = submission.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Initialize task metadata
    _progress.create_task(task_id, source_type="url", source_name=url)

    # Start processing in background thread
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, url, None, submission.max_duration_seconds, submission.whisper_model),
        daemon=True,
    )
    thread.start()

    logger.info(f"Task {task_id} started (URL: {url[:60]}...)")

    return TaskResponse(task_id=task_id, status="pending", message="Task queued for processing")


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get task status and progress.

    Reads from InMemoryProgressReporter (no Redis).
    """
    task_data = _progress.get_task(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(**task_data)


@router.get("/", response_model=list[TaskStatusResponse])
async def list_tasks(limit: int = 50, offset: int = 0):
    """
    List recent tasks.

    Reads from InMemoryProgressReporter (no Redis).
    """
    if limit < 1 or limit > 200:
        limit = 50
    if offset < 0:
        offset = 0

    tasks = _progress.list_tasks(limit=limit, offset=offset)

    return [TaskStatusResponse(**task) for task in tasks]

@router.api_route("/result/{filename}", methods=["GET", "HEAD", "DELETE"])
async def get_task_result(filename: str, request: Request):
    """
    Stream a result video file from storage/results/{filename}.
    Supports Range requests for seeking.
    """
    from pathlib import Path as _Path
    result_path = _storage.result_dir / filename
    if not result_path.exists():
        raise HTTPException(status_code=404, detail=f"Result not found: {filename}")

    file_size = result_path.stat().st_size

    # DELETE: удалить файл
    if request.method == "DELETE":
        import os as _os
        result_path.unlink(missing_ok=True)
        if _progress:
            for task in list(_progress.list_tasks()):
                if task.get("result_filename") == filename:
                    _progress._tasks.pop(task["task_id"], None)
                    if task["task_id"] in _progress._task_order:
                        _progress._task_order.remove(task["task_id"])
                    _progress._save_tasks()
        return {'deleted': filename, 'status': 'ok'}

    # HEAD: вернуть заголовки без тела
    if request.method == "HEAD":
        from starlette.responses import Response as _Resp
        return _Resp(
            status_code=200,
            headers={
                "Content-Length": str(file_size),
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
            },
        )

    range_header = request.headers.get("Range")

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "").split("-")
            start = int(range_val[0]) if range_val[0] else 0
            end = int(range_val[1]) if len(range_val) > 1 and range_val[1] else file_size - 1
        except (ValueError, IndexError):
            start, end = 0, file_size - 1

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_range():
            with open(result_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = f.read(min(1024 * 1024, remaining))
                    if not data:
                        break
                    yield data
                    remaining -= len(data)

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    def iter_file():
        with open(result_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )
