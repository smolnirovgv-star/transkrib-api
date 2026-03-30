import os
"""
Shared video processing pipeline.
Extracted from workers/tasks.py to be used by both Celery and standalone modes.
"""

import shutil
import logging
import tempfile
from pathlib import Path

from .config import settings
from .models.enums import TaskState
from .services.ffmpeg_service import FFmpegService
from .services.download_service import DownloadService
from .services.transcription_service import TranscriptionService
from .services.analysis_service import AnalysisService
from .services.storage_service import StorageService
from .utils.file_utils import safe_filename

logger = logging.getLogger("video_processor.pipeline")


def run_pipeline(
    task_id: str,
    video_path: Path,
    original_name: str,
    ffmpeg: FFmpegService,
    transcriber: TranscriptionService,
    analyzer: AnalysisService,
    storage: StorageService,
    progress,  # ProgressReporter or InMemoryProgressReporter
    max_duration_seconds: int | None = None,
    user_brief: dict | None = None,
):
    """
    Shared pipeline for both file uploads and URL downloads.

    Args:
        task_id: Unique task identifier
        video_path: Path to input video file
        original_name: Original filename for result naming
        ffmpeg: FFmpeg service instance
        transcriber: Transcription service instance
        analyzer: Analysis service instance
        storage: Storage service instance
        progress: Progress reporter (Redis-based or in-memory)
    """

    # Step 1: Convert to MP4
    progress.report(task_id, TaskState.CONVERTING, 0, "Конвертация в MP4...")
    proc_dir = storage.get_processing_dir(task_id)
    mp4_path = proc_dir / f"{safe_filename(original_name) or 'video'}.mp4"

    if video_path.suffix.lower() == ".mp4":
        if os.path.abspath(str(video_path)) != os.path.abspath(str(mp4_path)):
            shutil.copy2(str(video_path), str(mp4_path))
    else:
        if not ffmpeg.convert_to_mp4(video_path, mp4_path):
            raise RuntimeError(f"Conversion failed: {video_path.name}")
    progress.report(task_id, TaskState.CONVERTING, 100, "Конвертация завершена")

    # Step 2: Load Whisper model (lazy — only on first use), then transcribe
    progress.report(task_id, TaskState.LOADING_MODEL, 0, "Загрузка AI-движка...")
    logger.info(f"Whisper cache dir: {transcriber._download_root} (exists: {transcriber._download_root.exists() if transcriber._download_root else 'N/A'})")
    if transcriber._download_root and transcriber._download_root.exists():
        cached = [p.name for p in transcriber._download_root.iterdir() if p.is_dir()]
        logger.info(f"Cached faster-whisper models: {cached}")
    transcriber.ensure_model()
    progress.report(task_id, TaskState.TRANSCRIBING, 0, "Транскрибация...")
    transcript, language, raw_segments = transcriber.transcribe(
        mp4_path,
        on_progress=lambda s: progress.report(
            task_id,
            TaskState.TRANSCRIBING,
            50 if s == "starting" else 100,
            f"Транскрибация: {s}",
        ),
    )
    if not transcript:
        raise RuntimeError("Empty transcription")
    progress.report(
        task_id, TaskState.TRANSCRIBING, 100, f"Транскрипция готова ({language})"
    )

    # Step 3: Analyze via pause_detector + highlight_scorer (with fallback)
    progress.report(task_id, TaskState.ANALYZING, 0, "Анализ через Claude...")
    duration = ffmpeg.get_duration(mp4_path)
    if duration <= 0:
        raise RuntimeError("Could not determine video duration")

    _max_dur = max_duration_seconds if max_duration_seconds else settings.target_highlight_max_seconds
    fragments = None
    scored_segments = []

    if raw_segments:
        try:
            from .services.pause_detector import detect_pauses
            from .services.highlight_scorer import score_phrases, group_fragments
            phrases = detect_pauses(raw_segments)
            progress.report(task_id, TaskState.ANALYZING, 30, f"Оценка {len(phrases)} фраз...")
            scored = score_phrases(phrases, settings.anthropic_api_key, settings.claude_model, settings.claude_max_tokens, user_brief=user_brief)
            scored_segments = scored
            fragments = group_fragments(scored, duration, settings.target_highlight_ratio_min, settings.target_highlight_ratio_max, _max_dur)
            progress.report(task_id, TaskState.ANALYZING, 80, f"Сгруппировано {len(fragments)} клипов")
        except Exception as _se:
            logger.warning(f"highlight_scorer failed: {_se} — falling back to analyze_highlights")
            fragments = None

    if not fragments:
        fragments = analyzer.analyze_highlights(
            transcript, duration,
            settings.target_highlight_ratio_min, settings.target_highlight_ratio_max, _max_dur,
        )

    if not fragments:
        raise RuntimeError("Claude returned no fragments")
    progress.report(
        task_id, TaskState.ANALYZING, 100, f"Выбрано {len(fragments)} фрагментов"
    )

    # Step 4: Assemble
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    progress.report(task_id, TaskState.ASSEMBLING, 0, "Сборка видео...")
    result_filename = storage.generate_result_filename(original_name)
    result_path = storage.result_dir / result_filename

    # Save transcript text for preview generation (first 5000 chars)
    try:
        transcript_file = storage.result_dir / f"{result_path.stem}_transcript.txt"
        transcript_file.write_text(transcript[:5000], encoding="utf-8")
    except Exception as _te:
        logger.warning(f"Could not save transcript for preview: {_te}")

    # Save scored segments JSON for TranscriptViewer
    if scored_segments:
        try:
            import json as _json
            seg_file = storage.result_dir / f"{result_path.stem}_segments.json"
            seg_file.write_text(_json.dumps(scored_segments, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as _se:
            logger.warning(f"Could not save segments: {_se}")

    success = ffmpeg.cut_and_merge(
        mp4_path,
        fragments,
        result_path,
        settings.fade_duration,
        on_progress=lambda i, n: progress.report(
            task_id, TaskState.ASSEMBLING, i / n * 100, f"Фрагмент {i}/{n}"
        ),
        temp_dir=settings.temp_dir,
    )
    if not success or not result_path.exists():
        raise RuntimeError("Video assembly failed")

    # Done
    result_duration = ffmpeg.get_duration(result_path)
    size_mb = result_path.stat().st_size / (1024 * 1024)
    progress.report(
        task_id,
        TaskState.COMPLETED,
        100,
        f"Готово: {result_filename} ({size_mb:.1f} МБ)",
        result_filename=result_filename,
    )

    # Cleanup
    storage.cleanup_task(task_id)
    logger.info(f"Task {task_id} completed: {result_filename}")


def run_url_pipeline(
    task_id: str,
    url: str,
    ffmpeg: FFmpegService,
    transcriber: TranscriptionService,
    analyzer: AnalysisService,
    storage: StorageService,
    progress,  # ProgressReporter or InMemoryProgressReporter
    max_duration_seconds: int | None = None,
    user_brief: dict | None = None,
):
    """
    Pipeline for URL downloads (YouTube, VK, etc.) with download step.

    Args:
        task_id: Unique task identifier
        url: Video URL to download
        ffmpeg: FFmpeg service instance
        transcriber: Transcription service instance
        analyzer: Analysis service instance
        storage: Storage service instance
        progress: Progress reporter (Redis-based or in-memory)
    """

    # Step 0: Download
    progress.report(task_id, TaskState.DOWNLOADING, 0, f"Скачивание: {url[:60]}...")

    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(settings.temp_dir)) as tmp_dl:
        downloader = DownloadService(ffmpeg.ffmpeg_path)
        downloaded, title = downloader.download_url(
            url,
            Path(tmp_dl),
            on_progress=lambda p: progress.report(
                task_id, TaskState.DOWNLOADING, p, f"Скачивание: {p:.0f}%"
            ),
        )
        if not downloaded or not downloaded.exists():
            raise RuntimeError(f"Download failed: {url}")

        progress.report(task_id, TaskState.DOWNLOADING, 100, f"Скачано: {title}")

        # Copy to processing dir for pipeline
        proc_dir = storage.get_processing_dir(task_id)
        local_path = proc_dir / downloaded.name
        if os.path.abspath(str(downloaded)) != os.path.abspath(str(local_path)):
            shutil.copy2(str(downloaded), str(local_path))

    # Run main pipeline
    run_pipeline(
        task_id, local_path, title, ffmpeg, transcriber, analyzer, storage, progress,
        max_duration_seconds=max_duration_seconds,
        user_brief=user_brief,
    )
