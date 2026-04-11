"""Simple async task API for Telegram bot polling pattern.
Uses Groq Whisper API for fast transcription instead of local Whisper.
"""

import uuid
import asyncio
import os
import base64
import tempfile
import logging
import shutil
import httpx
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger("video_processor.bot_tasks")

router = APIRouter()

tasks_store: dict = {}

DOWNLOAD_TIMEOUT = 120

FORMATTING_PROMPT = """Ты — профессиональный редактор текста. Тебе дана сырая транскрипция видео/аудио.

Твоя задача — превратить её в красивый, структурированный текст для удобного чтения.

Правила форматирования:
1. Добавь краткий заголовок (тема текста) в начале, оберни его в <b>тег</b>
2. Раздели текст на логические абзацы (по 2-4 предложения)
3. Если в тексте есть несколько тем/разделов — добавь подзаголовки в <b>теги</b>
4. Исправь очевидные ошибки распознавания речи
5. Убери слова-паразиты (ну, типа, как бы, вот, э-э-э) если они не несут смысла
6. Сохрани весь смысл и содержание оригинала — ничего не добавляй от себя
7. Используй только HTML-теги: <b>жирный</b>, <i>курсив</i> — никакого Markdown
8. НЕ используй теги <h1>, <h2>, <p> — только <b> и <i> и простые переносы строк
9. Между абзацами ставь пустую строку

Верни ТОЛЬКО отформатированный текст, без пояснений."""


def format_with_claude_sync(raw_text: str) -> str:
    """Format raw transcription into structured readable text using Claude API."""
    api_key = os.environ.get("APP_ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[bot_tasks] APP_ANTHROPIC_API_KEY not set, skipping formatting")
        return raw_text

    text_to_format = raw_text[:12000]

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": FORMATTING_PROMPT + "\n\n---\n\nТранскрипция:\n\n" + text_to_format,
                        }
                    ],
                },
            )
            if resp.status_code != 200:
                logger.error("[bot_tasks] Claude formatting error %d: %s", resp.status_code, resp.text[:300])
                return raw_text
            data = resp.json()
            formatted = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    formatted += block["text"]
            return formatted if formatted.strip() else raw_text
    except Exception as e:
        logger.error("[bot_tasks] Claude formatting exception: %s", e)
        return raw_text


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


def _get_cookie_file() -> Optional[str]:
    """Decode YOUTUBE_COOKIES_B64 env var to a temp Netscape cookie file."""
    b64 = os.getenv("YOUTUBE_COOKIES_B64", "")
    if not b64:
        return None
    try:
        cookie_bytes = base64.b64decode(b64)
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
        with os.fdopen(fd, "wb") as f:
            f.write(cookie_bytes)
        logger.info(f"[bot_tasks] cookies file written: {path} ({len(cookie_bytes)} bytes)")
        return path
    except Exception as e:
        logger.warning(f"[bot_tasks] failed to decode YOUTUBE_COOKIES_B64: {e}")
        return None


def _download_with_ytdlp(url: str, task_id: str, cookie_path: Optional[str] = None) -> None:
    """Level 1: yt-dlp with ios/web_creator player_client."""
    import yt_dlp
    print(f"[bot_tasks] yt-dlp version: {yt_dlp.version.__version__}")
    logger.info(f"[bot_tasks] yt-dlp version: {yt_dlp.version.__version__}")

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
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web_creator"],
                "player_skip": ["webpage", "configs"],
            }
        },
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    logger.info("[bot_tasks] %s: Downloaded via yt-dlp+ios", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via yt-dlp+ios")


def _download_with_pytubefix(url: str, task_id: str) -> None:
    """Level 2: pytubefix fallback with PO token."""
    from pytubefix import YouTube as PyTube
    yt = PyTube(url, use_po_token=True)
    stream = yt.streams.get_audio_only()
    out_path = stream.download(output_path="/tmp", filename=task_id + "_pytube")
    target = "/tmp/" + task_id + ".mp3"
    shutil.move(out_path, target)
    logger.info("[bot_tasks] %s: Downloaded via pytubefix", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via pytubefix")


def _download_with_ytdlp_oauth(url: str, task_id: str) -> None:
    """Level 3: yt-dlp with oauth2 plugin."""
    import yt_dlp

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "/tmp/" + task_id,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
        ],
        "quiet": True,
        "no_warnings": True,
        "username": "oauth2",
        "password": "",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    logger.info("[bot_tasks] %s: Downloaded via yt-dlp+oauth2", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via yt-dlp+oauth2")


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    audio_path = "/tmp/" + task_id + ".mp3"
    cookies_file = None
    try:
        tasks_store[task_id]["status"] = "processing"
        tasks_store[task_id]["stage"] = "downloading"
        logger.info("[bot_tasks] %s: starting download for %s", task_id, url[:80])

        cookies_file = _get_cookie_file()
        logger.info("[bot_tasks] %s: cookies=%s", task_id, "yes" if cookies_file else "no")

        # Level 1: yt-dlp with ios/web_creator
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_download_with_ytdlp, url, task_id, cookies_file),
                timeout=DOWNLOAD_TIMEOUT,
            )
        except Exception as e1:
            logger.warning("[bot_tasks] %s: yt-dlp failed: %s", task_id, e1)
            print(f"[bot_tasks] {task_id}: yt-dlp failed: {e1}")
            # Level 2: pytubefix
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_download_with_pytubefix, url, task_id),
                    timeout=DOWNLOAD_TIMEOUT,
                )
            except Exception as e2:
                logger.warning("[bot_tasks] %s: pytubefix failed: %s", task_id, e2)
                print(f"[bot_tasks] {task_id}: pytubefix failed: {e2}")
                # Level 3: yt-dlp with oauth2
                await asyncio.wait_for(
                    asyncio.to_thread(_download_with_ytdlp_oauth, url, task_id),
                    timeout=DOWNLOAD_TIMEOUT,
                )

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

        tasks_store[task_id]["stage"] = "transcribing"

        text = await asyncio.to_thread(
            transcribe_with_groq_sync, audio_path, language
        )
        logger.info(
            "[bot_tasks] %s: transcription done (%d chars)", task_id, len(text)
        )

        tasks_store[task_id]["stage"] = "formatting"
        logger.info("[bot_tasks] %s: formatting with Claude...", task_id)
        formatted_text = await asyncio.to_thread(format_with_claude_sync, text)
        logger.info(
            "[bot_tasks] %s: formatting done (%d chars)", task_id, len(formatted_text)
        )

        tasks_store[task_id]["status"] = "done"
        tasks_store[task_id]["transcription"] = formatted_text

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
