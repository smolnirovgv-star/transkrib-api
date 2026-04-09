"""Simple async task API for Telegram bot polling pattern."""

import uuid
import asyncio
import os
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger("video_processor.bot_tasks")

router = APIRouter()

# In-memory task store
tasks_store: dict = {}


class TaskCreate(BaseModel):
    url: str
    cut_minutes: Optional[str] = None
    format: Optional[str] = "text"
    language: Optional[str] = "auto"


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    audio_path = f"/tmp/{task_id}.mp3"
    try:
        tasks_store[task_id]["status"] = "processing"

        import yt_dlp

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"/tmp/{task_id}",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "quiet": True,
        }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        await asyncio.to_thread(_download)
        logger.info(f"[bot_tasks] {task_id}: audio downloaded")

        from ..config import settings
        from ..services.transcription_service import TranscriptionService
        from pathlib import Path

        def _transcribe():
            svc = TranscriptionService(
                model_name=getattr(settings, "whisper_model", "tiny"),
            )
            svc.ensure_model()
            text, _srt, _segments = svc.transcribe(Path(audio_path))
            return text

        text = await asyncio.to_thread(_transcribe)
        logger.info(f"[bot_tasks] {task_id}: transcription done ({len(text)} chars)")

        tasks_store[task_id]["status"] = "done"
        tasks_store[task_id]["transcription"] = text

    except Exception as e:
        logger.error(f"[bot_tasks] {task_id}: error â {e}", exc_info=True)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = str(e)
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@router.post("/api/tasks/create")
async def create_task(body: TaskCreate, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks_store[task_id] = {"status": "pending", "task_id": task_id}
    background_tasks.add_task(
        run_transcription,
        task_id,
        body.url,
        body.cut_minutes,
        body.format,
        body.language,
    )
    logger.info(f"[bot_tasks] created task {task_id} for url={body.url[:60]}")
    return {"task_id": task_id, "status": "pending"}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    if task_id not in tasks_store:
        return {"status": "error", "error": "Task not found"}
    return tasks_store[task_id]
