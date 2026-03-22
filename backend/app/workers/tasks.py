"""Celery tasks: full video processing pipeline."""

import logging
from pathlib import Path

from .celery_app import celery_app
from .progress import ProgressReporter
from ..config import settings
from ..models.enums import TaskState
from ..services.ffmpeg_service import FFmpegService
from ..services.transcription_service import TranscriptionService
from ..services.analysis_service import AnalysisService
from ..services.storage_service import StorageService
from ..pipeline import run_pipeline, run_url_pipeline

logger = logging.getLogger("video_processor.tasks")

# Lazily initialized singletons (per-worker)
_ffmpeg: FFmpegService | None = None
_transcriber: TranscriptionService | None = None
_analyzer: AnalysisService | None = None
_storage: StorageService | None = None
_progress: ProgressReporter | None = None


def _get_services():
    global _ffmpeg, _transcriber, _analyzer, _storage, _progress
    if _ffmpeg is None:
        _ffmpeg = FFmpegService(settings.ffmpeg_path)
    if _transcriber is None:
        _transcriber = TranscriptionService(settings.whisper_model)
        _transcriber.ensure_model()
    if _analyzer is None:
        _analyzer = AnalysisService(
            settings.anthropic_api_key, settings.claude_model, settings.claude_max_tokens
        )
    if _storage is None:
        _storage = StorageService(
            settings.upload_dir, settings.processing_dir,
            settings.result_dir, settings.log_dir
        )
    if _progress is None:
        _progress = ProgressReporter(settings.celery_broker_url)
    return _ffmpeg, _transcriber, _analyzer, _storage, _progress


# NOTE: Pipeline logic moved to app/pipeline.py for reuse in standalone mode


@celery_app.task(bind=True, name="process_video")
def process_video_task(self, file_path: str, task_id: str, original_name: str):
    """Process an uploaded video file through the full pipeline."""
    ffmpeg, transcriber, analyzer, storage, progress = _get_services()
    try:
        run_pipeline(
            task_id, Path(file_path), original_name,
            ffmpeg, transcriber, analyzer, storage, progress
        )
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        progress.report(task_id, TaskState.FAILED, 0, str(e), error_message=str(e))
        raise


@celery_app.task(bind=True, name="process_url")
def process_url_task(self, url: str, task_id: str):
    """Download video from URL and process through the full pipeline."""
    ffmpeg, transcriber, analyzer, storage, progress = _get_services()
    try:
        run_url_pipeline(
            task_id, url,
            ffmpeg, transcriber, analyzer, storage, progress
        )
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        progress.report(task_id, TaskState.FAILED, 0, str(e), error_message=str(e))
        raise
