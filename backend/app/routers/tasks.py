"""Task management endpoints: create, status, list, cancel."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile, HTTPException

from ..config import settings
from ..models.schemas import TaskCreateFromUrl, TaskResponse, TaskStatusResponse
from ..models.enums import TaskState, SourceType
from ..workers.tasks import process_video_task, process_url_task
from ..workers.progress import ProgressReporter
from ..services.storage_service import StorageService
from ..services.download_service import DownloadService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_progress() -> ProgressReporter:
    return ProgressReporter(settings.celery_broker_url)


def _get_storage() -> StorageService:
    return StorageService(
        settings.upload_dir, settings.processing_dir,
        settings.result_dir, settings.log_dir,
    )


@router.post("/upload", response_model=TaskResponse, status_code=202)
async def create_task_from_file(file: UploadFile = File(...)):
    """Upload a video file to start processing."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.video_extensions:
        raise HTTPException(400, f"Unsupported format: {ext}. Supported: {settings.video_extensions}")

    storage = _get_storage()
    progress = _get_progress()

    content = await file.read()
    file_path, task_id = storage.save_upload(file.filename, content)

    now = datetime.now(timezone.utc)
    progress.create_task(task_id, SourceType.FILE.value, file.filename)

    # Dispatch Celery task
    process_video_task.delay(str(file_path), task_id, file.filename.rsplit(".", 1)[0])

    return TaskResponse(
        task_id=task_id,
        state=TaskState.PENDING,
        source_type=SourceType.FILE,
        source_name=file.filename,
        created_at=now,
    )


@router.post("/url", response_model=TaskResponse, status_code=202)
async def create_task_from_url(body: TaskCreateFromUrl):
    """Submit a URL (YouTube, VK, etc.) to start processing."""
    url = body.url.strip()
    if not url:
        raise HTTPException(400, "Empty URL")
    if not DownloadService.validate_url(url):
        raise HTTPException(400, f"Unsupported URL: {url}")

    progress = _get_progress()
    task_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    progress.create_task(task_id, SourceType.URL.value, url)

    # Dispatch Celery task
    process_url_task.delay(url, task_id)

    return TaskResponse(
        task_id=task_id,
        state=TaskState.PENDING,
        source_type=SourceType.URL,
        source_name=url,
        created_at=now,
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get current task status and progress."""
    progress = _get_progress()
    task = progress.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")

    return TaskStatusResponse(
        task_id=task["task_id"],
        state=TaskState(task["state"]),
        current_step=task.get("current_step") or None,
        progress_percent=float(task.get("progress_percent", 0)),
        step_details=task.get("step_details") or None,
        result_filename=task.get("result_filename") or None,
        error_message=task.get("error_message") or None,
        created_at=task.get("created_at", datetime.now(timezone.utc).isoformat()),
        updated_at=task.get("updated_at", datetime.now(timezone.utc).isoformat()),
    )


@router.get("/", response_model=list[TaskStatusResponse])
async def list_tasks(limit: int = 50, offset: int = 0):
    """List recent tasks."""
    progress = _get_progress()
    tasks = progress.list_tasks(limit, offset)
    result = []
    for t in tasks:
        result.append(TaskStatusResponse(
            task_id=t["task_id"],
            state=TaskState(t["state"]),
            current_step=t.get("current_step") or None,
            progress_percent=float(t.get("progress_percent", 0)),
            step_details=t.get("step_details") or None,
            result_filename=t.get("result_filename") or None,
            error_message=t.get("error_message") or None,
            created_at=t.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=t.get("updated_at", datetime.now(timezone.utc).isoformat()),
        ))
    return result
