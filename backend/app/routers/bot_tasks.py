"""Simple async task API for Telegram bot polling pattern.
Uses Groq Whisper API for fast transcription instead of local Whisper.
"""

import uuid
import asyncio
import os
import base64
import tempfile
import logging
import httpx
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger("video_processor.bot_tasks")

router = APIRouter()

# In-memory task store
tasks_store: dict = {}

DOWNLOAD_TIMEOUT = 120  # seconds


class TaskCreate(BaseModel):
    url: str
    cut_minutes: Optional[str] = None
    format: Optional[str] = "text"
    language: Optional[str] = "auto"


async def transcribe_with_groq(audio_path: str, language: str = "auto") -> str:
    """Transcribe audio using Groq Whisper API (free, ~3 sec)."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set in environment")

    api_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data = {
            "model": "whisper-large-v3-turbo",
            "response_format": "text",
        }
        if language and language != "auto":
            data["language"] = language

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {groq_key}"},
                files=files,
                data=data,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
            return resp.text


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    audio_path = f"/tmp/{task_id}.mp3"
    cookies_file = None
    try:
        tasks_store[task_id]["status"] = "processing"
        logger.info(f"[bot_tasks] {task_id}: starting download for {url[:80]}")

        import yt_dlp

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"/tmp/{task_id}",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 3,
            "extractor_retries": 3,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        }

        cookies_b64 = os.environ.get("YOUTUBE_COOKIES_B64")
        if cookies_b64:
            try:
                cookies_data = base64.b64decode(cookies_b64).decode("utf-8")
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
                tmp.write(cookies_data)
                tmp.close()
                cookies_file = tmp.name
                ydl_opts["cookiefile"] = cookies_file
            except Exception as ce:
                logger.warning(f"[bot_tasks] {task_id}: cookies error: {ce}")

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        await asyncio.wait_for(asyncio.to_thread(_download), timeout=DOWNLOAD_TIMEOUT)
        logger.info(f"[bot_tasks] {task_id}: audio downloaded OK")

        if not os.path.exists(audio_path):
            for ext in [".mp3", ".m4a", ".webm", ".opus"]:
                alt = f"/tmp/{task_id}{ext}"
                if os.path.exists(alt):
                    audio_path = alt
                    break
            else:
                raise FileNotFoundError(f"Audio not found at /tmp/{task_id}.*")

        file_size = os.path.getsize(audio_path)
        logger.info(f"[bot_tasks] {task_id}: audio {file_size} bytes, sending to Groq Whisper")

        text = await transcribe_with_groq(audio_path, language)
        logger.info(f"[bot_tasks] {task_id}: transcription done ({len(text)} chars)")

        tasks_store[task_id]["status"] = "done"
        tasks_store[task_id]["transcription"] = text

    except asyncio.TimeoutError:
        logger.error(f"[bot_tasks] {task_id}: TIMEOUT during download")
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = "Timeout: download took too long"
    except Exception as e:
        logger.error(f"[bot_tasks] {task_id}: error - {e}", exc_info=True)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = str(e)[:500]
    finally:
        for ext in [".mp3", ".m4a", ".webm", ".opus", ""]:
            p = f"/tmp/{task_id}{ext}"
            if os.path.exists(p):
                os.remove(p)
        if cookies_file and os.path.exists(cookies_file):
            os.remove(cookies_file)


@router.post("/api/tasks/create")
async def create_task(body: TaskCreate, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks_store[task_id] = {"status": "pending", "task_id": task_id}
    background_tasks.add_task(
        run_transcription, task_id, body.url,
        body.cut_minutes, body.format, body.language,
    )
    logger.info(f"[bot_tasks] created task {task_id} for url={body.url[:60]}")
    return {"task_id": task_id, "status": "pending"}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    if task_id not in tasks_store:
        return {"status": "error", "error": "Task not found"}
    return tasks_store[task_id]
