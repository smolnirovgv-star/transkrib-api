"""
Standalone task runner (без Celery) — для desktop режима.

Запускает pipeline в threading.Thread вместо Celery worker.
Управляет singleton-сервисами (ffmpeg, transcriber, analyzer, storage).
"""

import logging
import threading
from pathlib import Path

from ..config import settings
from ..models.enums import TaskState
from ..services.ffmpeg_service import FFmpegService
from ..services.transcription_service import TranscriptionService
from ..services.analysis_service import AnalysisService
from ..services.storage_service import StorageService
from ..pipeline import run_pipeline, run_url_pipeline

logger = logging.getLogger("video_processor.standalone_tasks")

# Singleton services (lazily initialized)
_services_lock = threading.Lock()
_ffmpeg: FFmpegService | None = None
_transcriber: TranscriptionService | None = None
_analyzer: AnalysisService | None = None
_storage: StorageService | None = None

# Shared progress reporter (injected from standalone_server.py)
_progress = None

# Trial manager (injected from standalone_server.py)
_trial_manager = None


def init_progress(progress):
    """
    Inject shared InMemoryProgressReporter.

    Called once at server startup from standalone_server.py.
    """
    global _progress
    _progress = progress
    logger.info("Standalone tasks initialized with in-memory progress reporter")


def init_trial_manager(trial_manager):
    """
    Inject TrialManager for post-processing recording.

    Called once at server startup from standalone_server.py.
    """
    global _trial_manager
    _trial_manager = trial_manager
    logger.info("Trial manager injected into standalone tasks")


def _get_services(whisper_model: str | None = None):
    """
    Lazily initializes and returns singleton services.

    Same pattern as workers/tasks.py _get_services().
    Thread-safe via lock.
    """
    global _ffmpeg, _transcriber, _analyzer, _storage

    with _services_lock:
        if _ffmpeg is None:
            logger.info("Initializing FFmpegService...")
            _ffmpeg = FFmpegService(settings.ffmpeg_path)

        requested_model = whisper_model or settings.whisper_model
        if _transcriber is None or _transcriber.model_name != requested_model:
            logger.info(f"Initializing TranscriptionService (model: {requested_model})...")
            _transcriber = TranscriptionService(requested_model, settings.whisper_cache_dir)
            # Model loading is deferred until first use (transcriber.transcribe calls ensure_model)
            # This avoids 30-60s startup delay

        if _analyzer is None:
            logger.info("Initializing AnalysisService...")
            _analyzer = AnalysisService(
                settings.anthropic_api_key,
                settings.claude_model,
                settings.claude_max_tokens,
            )

        if _storage is None:
            logger.info("Initializing StorageService...")
            _storage = StorageService(
                settings.upload_dir,
                settings.processing_dir,
                settings.result_dir,
                settings.log_dir,
            )

    return _ffmpeg, _transcriber, _analyzer, _storage, _progress


def run_video_task(task_id: str, file_path: str, original_name: str, max_duration_seconds: int | None = None, whisper_model: str | None = None):
    """
    Process uploaded video file through the pipeline.

    Runs in a background thread (called from standalone_tasks_router.py).

    Args:
        task_id: Unique task identifier
        file_path: Path to uploaded video file
        original_name: Original filename
    """
    ffmpeg, transcriber, analyzer, storage, progress = _get_services(whisper_model)

    try:
        logger.info(f"Starting video task {task_id}: {original_name}")
        run_pipeline(
            task_id,
            Path(file_path),
            original_name,
            ffmpeg,
            transcriber,
            analyzer,
            storage,
            progress,
            max_duration_seconds=max_duration_seconds,
        )
        logger.info(f"Task {task_id} completed successfully")
        if _trial_manager:
            _trial_manager.record_video()

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        progress.report(task_id, TaskState.FAILED, 0, str(e), error_message=str(e))


def run_url_task(task_id: str, url: str, max_duration_seconds: int | None = None, whisper_model: str | None = None):
    """
    Download and process video from URL through the pipeline.

    Runs in a background thread (called from standalone_tasks_router.py).

    Args:
        task_id: Unique task identifier
        url: Video URL (YouTube, VK, etc.)
    """
    ffmpeg, transcriber, analyzer, storage, progress = _get_services(whisper_model)

    try:
        logger.info(f"Starting URL task {task_id}: {url[:60]}...")
        run_url_pipeline(
            task_id, url, ffmpeg, transcriber, analyzer, storage, progress,
            max_duration_seconds=max_duration_seconds,
        )
        logger.info(f"Task {task_id} completed successfully")
        if _trial_manager:
            _trial_manager.record_video()

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        progress.report(task_id, TaskState.FAILED, 0, str(e), error_message=str(e))


def get_storage_service() -> StorageService:
    """Returns StorageService singleton (for routers)."""
    ffmpeg, transcriber, analyzer, storage, progress = _get_services()
    return storage


def preload_whisper_model() -> None:
    """Pre-load Whisper model into memory. Blocks until loaded. Call from lifespan."""
    _, transcriber, _, _, _ = _get_services()
    transcriber.ensure_model()
    logger.info("Whisper model pre-loaded and ready")
