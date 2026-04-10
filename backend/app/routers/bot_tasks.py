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

tasks_store: dict = {}

DOWNLOAD_TIMEOUT = 120


class TaskCreate(BaseModel):
    url: str
    cut_minutes: Optional[str] = None
    format: Optional[str] = "text"
    language: Optional[str] = "auto"


def transcribe_with_groq_sync(audio_path: str, language: str = "auto") -> str:
    """Transcribe audio using Groq Whisper API (synchronous)."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set in environment")

    api_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data = {"model": "whisper-large-v3-turbo", "response_format": "text"}
        if language and language != "auto":
            data["language"] = language

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                api_url,
                headers={"Authorization": "Bearer " + groq_key},
                files=files,
                data=data,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    "Groq API error " + str(resp.status_code) + ": " + resp.text[:300]
                )
            return resp.text


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    audio_path = "/tmp/" + task_id + ".mp3"
    cookies_file = None
    try:
        tasks_store[task_id]["status"] = "processing"
        logger.info("[bot_tasks] %s: starting download for %s", task_id, url[:80])

        import yt_dlp

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "/tmp/" + task_id,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
            ],
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 3,
            "extractor_retries": 3,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            "extractor_args": {"youtube": {"player_client": ["web", "android"]}},
        }

        cookies_b64 = os.environ.get("YOUTUBE_COOKIES_B64")
        if cookies_b64:
            try:
                cookies_data = base64.b64decode(cookies_b64).decode("utf-8")
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                )
                tmp.write(cookies_data)
                tmp.close()
                cookies_file = tmp.name
                ydl_opts["cookiefile"] = cookies_file
            except Exception as ce:
                logger.warning("[bot_tasks] %s: cookies error: %s", task_id, ce)

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        await asyncio.wait_for(
            asyncio.to_thread(_download), timeout=DOWNLOAD_TIMEOUT
        )
        logger.info("[bot_tasks] %s: audio downloaded OK", task_id)

        if not os.path.exists(audio_path):
            for ext in [".mp3", ".m4a", ".webm", ".opus"]:
                alt = "/tmp/" + task_id + ext
                if os.path.exists(alt):
                    audio_path = alt
                    break
            else:
                raise FileNotFoundError("Audio not found at /tmp/" + task_id + ".*")

        file_size = os.path.getsize(audio_path)
        logger.info(
            "[bot_tasks] %s: audio %d bytes, sending to Groq Whisper",
            task_id,
            file_size,
        )

        text = await asyncio.to_thread(
            transcribe_with_groq_sync, audio_path, language
        )
        logger.info(
            "[bot_tasks] %s: transcription done (%d chars)", task_id, len(text)
        )

        tasks_store[task_id]["status"] = "done"
        tasks_store[task_id]["transcription"] = text

    except asyncio.TimeoutError:
        logger.error("[bot_tasks] %s: TIMEOUT during download", task_id)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = "Timeout: download took too long"
    except Exception as e:
        logger.error("[bot_tasks] %s: error - %s", task_id, e, exc_info=True)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = str(e)[:500]
    finally:
        for ext in [".mp3", ".m4a", ".webm", ".opus", ""]:
            p = "/tmp/" + task_id + ext
            if os.path.exists(p):
                os.remove(p)
        if cookies_file and os.path.exists(cookies_file):
            os.remove(cookies_file)


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
    logger.info("[bot_tasks] created task %s for url=%s", task_id, body.url[:60])
    return {"task_id": task_id, "status": "pending"}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    if task_id not in tasks_store:
        return {"status": "error", "error": "Task not found"}
    return tasks_store[task_id]
