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
import requests
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


def download_via_cobalt(url: str, task_id: str) -> None:
    """Level 0: Download audio via cobalt.tools API -- works for YouTube from any IP."""
    print(f"=== DOWNLOAD FUNCTION cobalt: {url} ===")
    output_path = "/tmp/" + task_id + ".mp3"

    # Try multiple cobalt instances in order
    instances = [
        "https://api.cobalt.tools",
        "https://cobalt-api.kwiatekmiki.com",
        "https://cobalt.canine.tools",
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
    }

    last_error = None
    for api_url in instances:
        try:
            print(f"[Cobalt] Trying {api_url} for: {url}")
            resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
            print(f"[Cobalt] Response status: {resp.status_code}, body: {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status")
            if status == "error":
                raise Exception(f"Cobalt error: {data}")

            download_url = data.get("url")
            if not download_url:
                raise Exception(f"Cobalt: no URL in response: {data}")

            print(f"[Cobalt] Downloading from: {download_url[:100]}...")
            audio_resp = requests.get(download_url, timeout=180, stream=True)
            audio_resp.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in audio_resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(output_path)
            print(f"[Cobalt] Downloaded OK, size: {file_size} bytes")
            if file_size < 1000:
                raise Exception(f"Cobalt: file too small ({file_size} bytes)")

            print(f"[bot_tasks] {task_id}: Downloaded via cobalt ({api_url})")
            logger.info("[bot_tasks] %s: Downloaded via cobalt (%s)", task_id, api_url)
            return

        except Exception as e:
            print(f"[Cobalt] {api_url} failed: {e}")
            last_error = e
            continue

    raise Exception(f"All cobalt instances failed. Last error: {last_error}")


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
    """Level 1: yt-dlp with Chrome User-Agent and full error logging."""
    import glob
    import yt_dlp
    print(f"=== DOWNLOAD FUNCTION yt-dlp: {url} ===")
    logger.info("[bot_tasks] yt-dlp version: %s", yt_dlp.version.__version__)

    output_template = "/tmp/" + task_id + ".%(ext)s"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    # Use cookie_path from caller, or fall back to YOUTUBE_COOKIES env var
    tmp_cookiefile = None
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path
        logger.info("[DOWNLOAD] Using cookies from caller (YOUTUBE_COOKIES_B64)")
    else:
        cookies_content = os.getenv("YOUTUBE_COOKIES", "")
        if cookies_content:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, dir="/tmp"
            )
            tmp.write(cookies_content)
            tmp.close()
            tmp_cookiefile = tmp.name
            ydl_opts["cookiefile"] = tmp_cookiefile
            logger.info("[DOWNLOAD] Using YouTube cookies from YOUTUBE_COOKIES env")
        else:
            logger.info("[DOWNLOAD] No cookies available (set YOUTUBE_COOKIES or YOUTUBE_COOKIES_B64)")

    logger.info("[DOWNLOAD] Starting yt-dlp for: %s", url)
    logger.info("[DOWNLOAD] Output template: %s", output_template)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            logger.info("[DOWNLOAD] yt-dlp completed. Title: %s", info.get("title", "unknown"))
            logger.info("[DOWNLOAD] Format: %s, Ext: %s", info.get("format", "?"), info.get("ext", "?"))
    except Exception as e:
        logger.error("[DOWNLOAD] yt-dlp FAILED: %s: %s", type(e).__name__, e)
        raise
    finally:
        if tmp_cookiefile and os.path.exists(tmp_cookiefile):
            os.unlink(tmp_cookiefile)

    files_found = glob.glob("/tmp/" + task_id + ".*")
    logger.info("[DOWNLOAD] Files matching /tmp/%s.*: %s", task_id, files_found)
    all_tmp = [f for f in os.listdir("/tmp") if task_id[:8] in f]
    logger.info("[DOWNLOAD] All /tmp files with task_id prefix: %s", all_tmp)

    logger.info("[bot_tasks] %s: Downloaded via yt-dlp", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via yt-dlp")


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    print("=== RUN_TRANSCRIPTION CALLED ===")
    print(f"=== task_id={task_id} url={url} ===")
    audio_path = "/tmp/" + task_id + ".mp3"
    cookies_file = None
    try:
        tasks_store[task_id]["status"] = "processing"
        tasks_store[task_id]["stage"] = "downloading"
        tasks_store[task_id]["debug_log"] = "run_transcription started"
        logger.info("[bot_tasks] %s: starting download for %s", task_id, url[:80])

        cookies_file = _get_cookie_file()
        logger.info("[bot_tasks] %s: cookies=%s", task_id, "yes" if cookies_file else "no")

        print(f"[Download] URL: {url}")
        is_youtube = "youtube.com" in url or "youtu.be" in url
        print(f"[Download] is_youtube check: 'youtube.com' in url = {'youtube.com' in url}, 'youtu.be' in url = {'youtu.be' in url}")
        print(f"[Download] is_youtube = {is_youtube}")

        # Level 0: Cobalt API (YouTube only)
        if is_youtube:
            print("[Download] Trying Level 0: cobalt.tools")
            tasks_store[task_id]["debug_log"] = "cobalt: trying api.cobalt.tools..."
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(download_via_cobalt, url, task_id),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                print("[Download] Cobalt SUCCESS")
                tasks_store[task_id]["debug_log"] = "cobalt: SUCCESS"
            except Exception as e0:
                logger.warning("[bot_tasks] %s: cobalt failed: %s", task_id, e0)
                print(f"[Download] Cobalt FAILED: {e0}")
                tasks_store[task_id]["debug_log"] = f"cobalt FAILED: {str(e0)[:200]}"
        else:
            print("[Download] Skipping cobalt (not YouTube)")
            tasks_store[task_id]["debug_log"] = "cobalt skipped (not YouTube)"

        if not os.path.exists("/tmp/" + task_id + ".mp3"):
            # Level 1: yt-dlp with ios/web_creator
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_download_with_ytdlp, url, task_id, cookies_file),
                    timeout=DOWNLOAD_TIMEOUT,
                )
            except Exception as e1:
                logger.error("[bot_tasks] %s: yt-dlp failed: %s", task_id, e1)
                print(f"[bot_tasks] {task_id}: yt-dlp failed: {e1}")
                raise

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
