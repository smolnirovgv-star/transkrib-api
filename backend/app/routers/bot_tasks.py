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
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from collections import deque
_LOG_BUFFER = deque(maxlen=500)

class _BufferHandler(logging.Handler):
    def emit(self, record):
        _LOG_BUFFER.append({
            "t": self.formatter.formatTime(record, "%H:%M:%S") if self.formatter else "",
            "lvl": record.levelname,
            "msg": self.format(record),
        })

_buf_handler = _BufferHandler()
_buf_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(_buf_handler)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    HAS_TRANSCRIPT_API = True
    logger.info("[STARTUP] youtube-transcript-api imported OK")
except ImportError as _e:
    HAS_TRANSCRIPT_API = False
    logger.error("[STARTUP] youtube-transcript-api NOT AVAILABLE: %s", _e)

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
        logger.warning("[COOKIES] YOUTUBE_COOKIES_B64 not set")
        return None
    try:
        cookie_bytes = base64.b64decode(b64)
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
        with os.fdopen(fd, "wb") as f:
            f.write(cookie_bytes)
        first_line = cookie_bytes[:50].decode("utf-8", errors="replace").split("\n")[0]
        has_netscape = b"Netscape HTTP Cookie File" in cookie_bytes[:100]
        has_tabs = b"\t" in cookie_bytes
        line_count = cookie_bytes.count(b"\n")
        logger.info("[COOKIES] Written %d bytes, %d lines, has_netscape=%s, has_tabs=%s, first=%r",
            len(cookie_bytes), line_count, has_netscape, has_tabs, first_line[:60])
        if not has_tabs:
            logger.error("[COOKIES] WARNING: no TAB chars in cookie file — format likely broken!")
        if not has_netscape:
            logger.error("[COOKIES] WARNING: missing Netscape HTTP Cookie File header!")
        return path
    except Exception as e:
        logger.warning("[COOKIES] failed to decode YOUTUBE_COOKIES_B64: %s", e)
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

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path
        logger.info("[DOWNLOAD] Using cookies from YOUTUBE_COOKIES_B64 (base64)")
    else:
        logger.info("[DOWNLOAD] No cookies (YOUTUBE_COOKIES_B64 not set)")

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
        pass

    files_found = glob.glob("/tmp/" + task_id + ".*")
    logger.info("[DOWNLOAD] Files matching /tmp/%s.*: %s", task_id, files_found)
    all_tmp = [f for f in os.listdir("/tmp") if task_id[:8] in f]
    logger.info("[DOWNLOAD] All /tmp files with task_id prefix: %s", all_tmp)

    logger.info("[bot_tasks] %s: Downloaded via yt-dlp", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via yt-dlp")


def _get_youtube_transcript(url: str, lang: str = "ru") -> str:
    """Get subtitles directly from YouTube without downloading audio."""
    if not HAS_TRANSCRIPT_API:
        raise ImportError("youtube-transcript-api not installed")
    video_id = None
    for p in [r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", r"(?:embed/)([a-zA-Z0-9_-]{11})"]:
        m = re.search(p, url)
        if m:
            video_id = m.group(1)
            break
    if not video_id:
        raise ValueError(f"Cannot extract video ID from: {url}")
    logger.info("[TRANSCRIPT-API] Getting transcript for %s, lang=%s", video_id, lang)

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    cookie_path = _get_cookie_file()
    try:
        if cookie_path:
            import http.cookiejar as _cj
            cj = _cj.MozillaCookieJar(cookie_path)
            cj.load(ignore_discard=True, ignore_expires=True)
            for cookie in cj:
                session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
            logger.info("[TRANSCRIPT-API] Loaded %d cookies into session", len(session.cookies))
        ytt_api = YouTubeTranscriptApi(http_client=session)
        transcript = ytt_api.fetch(video_id, languages=[lang, "en", "ru"])
        full_text = " ".join([entry.text for entry in transcript])
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.unlink(cookie_path)

    logger.info("[TRANSCRIPT-API] Got %d chars", len(full_text))
    return full_text


async def run_transcription(task_id: str, url: str, cut_minutes, fmt, language):
    print("=== RUN_TRANSCRIPTION CALLED ===")
    print(f"=== task_id={task_id} url={url} ===")
    audio_path = "/tmp/" + task_id + ".mp3"
    cookies_file = None
    raw_text = None
    try:
        tasks_store[task_id]["status"] = "processing"
        tasks_store[task_id]["stage"] = "downloading"
        tasks_store[task_id]["debug_log"] = "run_transcription started"
        logger.info("[bot_tasks] %s: starting for %s", task_id, url[:80])

        is_youtube = "youtube.com" in url or "youtu.be" in url
        print(f"[Download] URL: {url}, is_youtube={is_youtube}")

        # Step 1: Try YouTube Transcript API directly (fast, no audio download)
        if is_youtube and HAS_TRANSCRIPT_API:
            try:
                logger.info("[TRANSCRIPT-API] %s: trying direct transcript for: %s", task_id, url)
                raw_text = await asyncio.to_thread(
                    _get_youtube_transcript, url, language or "ru"
                )
                logger.info("[TRANSCRIPT-API] %s: SUCCESS! Got %d chars", task_id, len(raw_text))
                tasks_store[task_id]["debug_log"] = "transcript-api: SUCCESS"
            except Exception as et:
                logger.warning("[TRANSCRIPT-API] %s: failed: %s — falling back to audio download", task_id, et)
                tasks_store[task_id]["debug_log"] = f"transcript-api FAILED: {str(et)[:200]}"
                raw_text = None
        elif is_youtube and not HAS_TRANSCRIPT_API:
            logger.warning("[TRANSCRIPT-API] %s: library not available, skipping to audio download", task_id)

        # Step 2: If no transcript — download audio + Groq (fallback)
        if not raw_text:
            cookies_file = _get_cookie_file()
            logger.info("[bot_tasks] %s: cookies=%s", task_id, "yes" if cookies_file else "no")

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
                # Level 1: yt-dlp
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
            raw_text = await asyncio.to_thread(
                transcribe_with_groq_sync, audio_path, language
            )
            logger.info(
                "[bot_tasks] %s: groq transcription done (%d chars)", task_id, len(raw_text)
            )

        # Step 3: Format with Claude
        tasks_store[task_id]["stage"] = "formatting"
        logger.info("[bot_tasks] %s: formatting with Claude...", task_id)
        formatted_text = await asyncio.to_thread(format_with_claude_sync, raw_text)
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

@router.get("/api/debug/logs")
async def get_debug_logs(n: int = 100):
    """Return last N log lines from in-memory buffer."""
    lines = list(_LOG_BUFFER)[-n:]
    return {"count": len(lines), "logs": lines}


@router.get("/api/debug/logs/clear")
async def clear_debug_logs():
    _LOG_BUFFER.clear()
    return {"cleared": True}
