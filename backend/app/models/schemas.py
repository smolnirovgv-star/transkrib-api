"""Pydantic schemas for API request/response models."""

from datetime import datetime
from pydantic import BaseModel

from .enums import TaskState, SourceType


class TaskCreateFromUrl(BaseModel):
    url: str


class TaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    message: str = ""


class TaskStatusResponse(BaseModel):
    task_id: str
    state: TaskState
    current_step: str | None = None
    progress_percent: float = 0.0
    step_details: str | None = None
    result_filename: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ProgressUpdate(BaseModel):
    """Sent over WebSocket."""
    task_id: str
    state: TaskState
    step: str
    progress: float  # 0.0 - 100.0
    message: str
    timestamp: datetime


class ResultItem(BaseModel):
    filename: str
    size_mb: float
    duration_seconds: float
    duration_formatted: str
    created_at: str
    source_name: str | None = None


class SystemInfo(BaseModel):
    ffmpeg_version: str | None
    whisper_model: str
    claude_model: str
    storage_used_mb: float
    results_count: int
