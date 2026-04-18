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

DOWNLOAD_TIMEOUT = 600

FORMATTING_PROMPT = """Ты — профессиональный редактор. Тебе дана сырая транскрипция видео/аудио для Telegram.

Правила форматирования (только HTML-теги Telegram: <b>, <i>, никакого Markdown):

1. Первая строка — краткий заголовок темы: <b>🎯 Название темы</b>
2. Раздели текст на логические блоки по 2-4 предложения, между блоками — пустая строка
3. Каждый новый раздел начинай с подзаголовка: <b>📌 Название раздела</b>
4. Ключевые мысли выделяй: <i>важная мысль</i>
5. Если есть перечисление — используй:
   • пункт первый
   • пункт второй
6. Исправь ошибки распознавания речи
7. Убери слова-паразиты (ну, типа, как бы, э-э-э)
8. Сохрани весь смысл оригинала — ничего не добавляй от себя
9. В конце добавь итоговую строку: <b>💡 Главная мысль:</b> одно предложение-резюме

Верни ТОЛЬКО отформатированный текст, без пояснений."""


def _is_speech_present(raw_text: str, duration_seconds: int) -> bool:
    if not raw_text or len(raw_text.strip()) < 20:
        return False
    minutes = max(1, duration_seconds // 60)
    chars_per_minute = len(raw_text) / minutes
    return chars_per_minute >= 50


def format_with_claude_sync(raw_text: str) -> tuple:
    """Format raw transcription. Returns (text, input_tokens, output_tokens, cost_usd)."""
    api_key = os.environ.get("APP_ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[bot_tasks] APP_ANTHROPIC_API_KEY not set, skipping formatting")
        return raw_text, 0, 0, 0.0

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
                return raw_text, 0, 0, 0.0
            data = resp.json()
            formatted = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    formatted += block["text"]
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost_usd = (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000
            logger.info("[CLAUDE_USAGE] input=%d output=%d cost=$%.4f", input_tokens, output_tokens, cost_usd)
            result_text = formatted if formatted.strip() else raw_text
            return result_text, input_tokens, output_tokens, cost_usd
    except Exception as e:
        logger.error("[bot_tasks] Claude formatting exception: %s", e)
        return raw_text, 0, 0, 0.0


def analyze_chunks_with_claude(
    raw_text,
    target_minutes,
    total_duration_seconds
):
    """Analyse transcript, return chunking plan."""
    api_key = os.environ.get("APP_ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "API key not set"}

    total_minutes = max(1, total_duration_seconds // 60)
    nl = chr(10)
    prompt = (
        "You are a video content editor. Analyse the video transcript." + nl + nl
        + "TASK:" + nl
        + "1. Split into semantic blocks" + nl
        + "2. Rate importance 1-10" + nl
        + f"3. Select blocks fitting in {target_minutes} min" + nl
        + "4. Identify left-out important blocks" + nl + nl
        + f"Video duration: {total_minutes} min, Target: {target_minutes} min" + nl + nl
        + "Transcript:" + nl + raw_text[:8000] + nl + nl
        + "Reply ONLY in JSON (no markdown):" + nl
        + '{"chunks":[{"start_time","end_time","topic","importance","include"}],' + nl
        + '"kept_minutes","lost_important_count","suggestion_minutes","warning_type","warning_message"}' + nl + nl
        + "warning_type: loss | surplus | ok"
    )

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
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if resp.status_code != 200:
            logger.error("[CHUNKS] Claude error %d: %s", resp.status_code, resp.text[:200])
            return {"error": f"Claude error {resp.status_code}"}
        data = resp.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        import json as _json
        text = text.strip()
        t3 = chr(96) * 3
        if text.startswith(t3):
            text = text.split(t3)[1]
            if text.startswith("json"):
                text = text[4:]
        result = _json.loads(text.strip())
        logger.info("[CHUNKS] done: %d chunks, kept=%.1f min, warning=%s",
            len(result.get("chunks", [])), result.get("kept_minutes", 0),
            result.get("warning_type", "?"))
        return result
    except Exception as e:
        logger.error("[CHUNKS] error: %s", e)
        return {"error": str(e)}


class TaskCreate(BaseModel):
    url: str
    cut_minutes: Optional[str] = None
    format: Optional[str] = "text"
    language: Optional[str] = "auto"


def _fmt_srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_with_groq_sync(audio_path: str, language: str = "auto", output_format: str = "text") -> str:
    """Transcribe audio using Groq Whisper API (synchronous)."""
    import time
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set in environment")

    api_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    for attempt in range(3):
        try:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
                if output_format == "srt":
                    data = {
                        "model": "whisper-large-v3",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                    }
                else:
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
                    if output_format == "srt":
                        segments = resp.json().get("segments", [])
                        srt_lines = []
                        for i, seg in enumerate(segments, 1):
                            srt_lines.append(str(i))
                            srt_lines.append(f"{_fmt_srt_time(seg['start'])} --> {_fmt_srt_time(seg['end'])}")
                            srt_lines.append(seg["text"].strip())
                            srt_lines.append("")
                        return "\n".join(srt_lines)
                    return resp.text
        except Exception as e:
            logger.warning("[GROQ] attempt %d/3 failed: %s", attempt + 1, str(e)[:200])
            if attempt < 2:
                time.sleep(5)
            else:
                raise




def _get_cookie_file() -> Optional[str]:
    """Decode YOUTUBE_COOKIES_B64 to a temp Netscape cookie file.
    Reads from env var first, then from Render Secret File at /etc/secrets/YOUTUBE_COOKIES_B64.
    """
    b64 = os.getenv("YOUTUBE_COOKIES_B64", "").strip()

    if not b64:
        secret_path = "/etc/secrets/YOUTUBE_COOKIES_B64"
        if os.path.exists(secret_path):
            with open(secret_path, "r") as f:
                b64 = f.read().strip()
            logger.info("[COOKIES] Loaded YOUTUBE_COOKIES_B64 from secret file")
            # Handle KEY=VALUE format if secret file was saved as .env style
            if b64.startswith("YOUTUBE_COOKIES_B64="):
                b64 = b64[len("YOUTUBE_COOKIES_B64="):]
        else:
            logger.warning("[COOKIES] YOUTUBE_COOKIES_B64 not set (no env var, no secret file)")
            return None

    try:
        if b64.strip().startswith('#'):
            cookie_bytes = b64.encode('utf-8')
            logger.info("[COOKIES] Detected plain text cookies (starts with #)")
        else:
            cookie_bytes = base64.b64decode(b64)
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
        with os.fdopen(fd, "wb") as f:
            f.write(cookie_bytes)
        first_line = cookie_bytes[:50].decode("utf-8", errors="replace").split("\n")[0]
        has_netscape = b"Netscape HTTP Cookie File" in cookie_bytes[:100]
        has_tabs = b"\t" in cookie_bytes
        line_count = cookie_bytes.count(b"\n")
        logger.info(
            "[COOKIES] Written %d bytes, %d lines, has_netscape=%s, has_tabs=%s, first=%r",
            len(cookie_bytes), line_count, has_netscape, has_tabs, first_line[:60],
        )
        if not has_tabs:
            logger.error("[COOKIES] WARNING: no TAB chars — format likely broken!")
        if not has_netscape:
            logger.error("[COOKIES] WARNING: missing Netscape HTTP Cookie File header!")
        return path
    except Exception as e:
        logger.warning("[COOKIES] failed to decode YOUTUBE_COOKIES_B64: %s", e)
        return None


def _download_with_ytdlp(url: str, task_id: str, cookie_path: Optional[str] = None):
    """Level 1: yt-dlp with Chrome User-Agent and full error logging."""
    import glob
    import yt_dlp
    print(f"=== DOWNLOAD FUNCTION yt-dlp: {url} ===")
    logger.info("[bot_tasks] yt-dlp version: %s", yt_dlp.version.__version__)

    output_template = "/tmp/" + task_id + ".%(ext)s"

    ydl_opts = {
        "format": "worstaudio/bestaudio/best",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "extract_flat": False,
        "retries": 3,
        "throttledratelimit": 0,
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

    # Check file size — Groq limit is 25MB
    audio_path = "/tmp/" + task_id + ".mp3"
    if os.path.exists(audio_path):
        file_size = os.path.getsize(audio_path)
        logger.info("[DOWNLOAD] File size: %.1f MB", file_size / 1024 / 1024)
        if file_size > 24 * 1024 * 1024:
            import subprocess, math, json as _json
            logger.warning("[DOWNLOAD] File too large (%.1f MB), splitting into chunks", file_size / 1024 / 1024)
            # Get duration via ffprobe
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", audio_path
            ], capture_output=True, text=True, check=True)
            duration_sec = float(_json.loads(result.stdout)["format"]["duration"])
            chunk_duration = 600  # 10 minutes per chunk
            num_chunks = math.ceil(duration_sec / chunk_duration)
            logger.info("[DOWNLOAD] Splitting into %d chunks of %d sec", num_chunks, chunk_duration)
            chunk_paths = []
            for i in range(num_chunks):
                start = i * chunk_duration
                chunk_path = audio_path.rsplit(".", 1)[0] + f"_chunk{i}.mp3"
                subprocess.run([
                    "ffmpeg", "-i", audio_path,
                    "-ss", str(start), "-t", str(chunk_duration),
                    "-acodec", "libmp3lame", "-q:a", "9",
                    chunk_path, "-y"
                ], check=True, capture_output=True)
                chunk_paths.append(chunk_path)
                logger.info("[DOWNLOAD] Chunk %d: %.1f MB", i + 1, os.path.getsize(chunk_path) / 1024 / 1024)
            os.remove(audio_path)
            logger.info("[bot_tasks] %s: Downloaded via yt-dlp (chunked)", task_id)
            return chunk_paths

    logger.info("[bot_tasks] %s: Downloaded via yt-dlp", task_id)
    print(f"[bot_tasks] {task_id}: Downloaded via yt-dlp")


def _get_transcript_supadata(url: str) -> str:
    """Get YouTube transcript via Supadata API — works from any IP, no proxy needed."""
    api_key = os.getenv("SUPADATA_API_KEY", "")
    if not api_key:
        raise ValueError("SUPADATA_API_KEY not set")

    import urllib.parse
    encoded_url = urllib.parse.quote(url, safe="")
    api_url = f"https://api.supadata.ai/v1/transcript?url={encoded_url}&text=true"

    logger.info("[SUPADATA] Fetching transcript for: %s", url[:80])
    resp = requests.get(api_url, headers={"x-api-key": api_key}, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"Supadata error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    text = data.get("content", "")
    if not text:
        raise RuntimeError(f"Supadata: empty content in response: {str(data)[:200]}")

    logger.info("[SUPADATA] Got %d chars", len(text))
    return text


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
        proxy_url = os.getenv("YOUTUBE_PROXY", "").strip()
        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}
            logger.info("[TRANSCRIPT-API] Using proxy: %s", proxy_url[:40])
        else:
            logger.info("[TRANSCRIPT-API] No proxy configured (YOUTUBE_PROXY not set)")
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

        # Normalize vkvideo.ru -> vk.com/video (Supadata supports vk.com but not vkvideo.ru)
        if "vkvideo.ru/video" in url:
            url = url.replace("vkvideo.ru/video", "vk.com/video")
            logger.info("[URL] Normalized vkvideo.ru -> vk.com/video: %s", url)
            tasks_store[task_id]["url"] = url

        logger.info("[bot_tasks] %s: starting for %s", task_id, url[:80])
        logger.info("[FORMAT] task_id=%s fmt=%r output_format=%s",
            task_id, fmt, "srt" if fmt == "fmt_srt" else "text")
        output_format = "srt" if fmt == "fmt_srt" else "text"  # fmt_md treated as text

        # Check video duration before processing
        try:
            import yt_dlp as ytdlp
            with ytdlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get("duration", 0)
                tasks_store[task_id]["duration_seconds"] = duration
                logger.info("[DURATION] Video duration: %d seconds (%.1f hours)", duration, duration / 3600)
                if duration > 3 * 3600:  # > 3 hours
                    hours = duration / 3600
                    tasks_store[task_id]["status"] = "error"
                    tasks_store[task_id]["result"] = (
                        f"⚠️ Видео слишком длинное ({hours:.1f} ч).\n\n"
                        f"Максимальная длина для обработки — <b>3 часа</b>.\n"
                        f"Пожалуйста, разделите видео на части по <b>1 часу</b> и отправьте каждую часть отдельно."
                    )
                    return
        except Exception as ed:
            logger.warning("[DURATION] Could not check duration: %s", ed)

        if tasks_store[task_id].get("status") == "cancelled":
            logger.info("[bot_tasks] %s: task cancelled by user", task_id)
            return

        is_youtube = "youtube.com" in url or "youtu.be" in url
        print(f"[Download] URL: {url}, is_youtube={is_youtube}")

        # Step 1a: Try Supadata API first (works from any IP, no proxy)
        is_supadata_supported = is_youtube or "vk.com/video" in url or "vkvideo.ru" in url
        if is_supadata_supported and os.getenv("SUPADATA_API_KEY") and not raw_text and fmt != "fmt_srt":
            try:
                logger.info("[SUPADATA] %s: trying Supadata for: %s", task_id, url)
                raw_text = await asyncio.to_thread(_get_transcript_supadata, url)
                logger.info("[SUPADATA] %s: SUCCESS! Got %d chars", task_id, len(raw_text))
                tasks_store[task_id]["debug_log"] = "supadata: SUCCESS"
            except Exception as es:
                logger.warning("[SUPADATA] %s: failed: %s — trying transcript-api", task_id, es)
                tasks_store[task_id]["debug_log"] = f"supadata FAILED: {str(es)[:200]}"
                raw_text = None

        if tasks_store[task_id].get("status") == "cancelled":
            logger.info("[bot_tasks] %s: task cancelled by user", task_id)
            return

        # Step 1b: Try YouTube Transcript API directly (fast, no audio download)
        if not raw_text and is_youtube and HAS_TRANSCRIPT_API:
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
        elif not raw_text and is_youtube and not HAS_TRANSCRIPT_API:
            logger.warning("[TRANSCRIPT-API] %s: library not available, skipping to audio download", task_id)

        # Step 2: If no transcript — download audio + Groq (fallback)
        if not raw_text:
            cookies_file = _get_cookie_file()
            logger.info("[bot_tasks] %s: cookies=%s", task_id, "yes" if cookies_file else "no")

            # Level 1: yt-dlp
            try:
                download_result = await asyncio.wait_for(
                    asyncio.to_thread(_download_with_ytdlp, url, task_id, cookies_file),
                    timeout=DOWNLOAD_TIMEOUT,
                )
            except Exception as e1:
                logger.error("[bot_tasks] %s: yt-dlp failed: %s", task_id, e1)
                print(f"[bot_tasks] {task_id}: yt-dlp failed: {e1}")
                raise

            if tasks_store[task_id].get("status") == "cancelled":
                logger.info("[bot_tasks] %s: task cancelled by user", task_id)
                return

            tasks_store[task_id]["stage"] = "transcribing"
            if isinstance(download_result, list):
                # Multiple chunks — transcribe each and combine
                chunk_texts = []
                for i, chunk_path in enumerate(download_result):
                    logger.info("[GROQ] Transcribing chunk %d/%d", i + 1, len(download_result))
                    chunk_text = await asyncio.to_thread(
                        transcribe_with_groq_sync, chunk_path, language, output_format
                    )
                    chunk_texts.append(chunk_text)
                    os.remove(chunk_path)
                    if tasks_store[task_id].get("status") == "cancelled":
                        logger.info("[bot_tasks] %s: task cancelled by user", task_id)
                        return
                if output_format == "srt":
                    # Renumber SRT blocks sequentially across chunks
                    combined_lines = []
                    counter = 1
                    for chunk_srt in chunk_texts:
                        lines = chunk_srt.strip().splitlines()
                        j = 0
                        while j < len(lines):
                            if lines[j].strip().isdigit():
                                combined_lines.append(str(counter))
                                counter += 1
                                j += 1
                                while j < len(lines) and lines[j].strip() != "":
                                    combined_lines.append(lines[j])
                                    j += 1
                                combined_lines.append("")
                            else:
                                j += 1
                    raw_text = "\n".join(combined_lines)
                else:
                    raw_text = " ".join(chunk_texts)
                logger.info("[GROQ] All chunks transcribed, total: %d chars", len(raw_text))
            else:
                # Single file
                if not os.path.exists(audio_path):
                    for ext in [".mp3", ".m4a", ".webm", ".opus"]:
                        alt = "/tmp/" + task_id + ext
                        if os.path.exists(alt):
                            audio_path = alt
                            break
                    else:
                        raise FileNotFoundError("Audio not found at /tmp/" + task_id + ".*")
                file_size = os.path.getsize(audio_path)
                logger.info("[bot_tasks] %s: audio %d bytes, sending to Groq Whisper", task_id, file_size)
                raw_text = await asyncio.to_thread(
                    transcribe_with_groq_sync, audio_path, language, output_format
                )
                logger.info("[bot_tasks] %s: groq transcription done (%d chars)", task_id, len(raw_text))

        # Speech detection
        duration_sec = tasks_store[task_id].get("duration_seconds", 0)
        if not _is_speech_present(raw_text, duration_sec):
            logger.info("[bot_tasks] %s: no speech detected", task_id)
            tasks_store[task_id]["status"] = "no_speech"
            tasks_store[task_id]["transcription"] = (
                "🎬 В этом видео не обнаружена речь человека.\n\n"
                "Transkrib работает с видео где есть голос. "
                "Для видео без речи (природа, стройка, музыка) — "
                "скоро появится Vision-анализ.\n\n"
                "Попробуйте другое видео!"
            )
            return

        # Step 3: Format with Claude (skip for SRT - return raw timestamps)
        if output_format == "srt":
            logger.info("[bot_tasks] %s: SRT format - skipping Claude, returning raw SRT", task_id)
            tasks_store[task_id]["status"] = "done"
            tasks_store[task_id]["transcription"] = raw_text
        else:
            tasks_store[task_id]["stage"] = "formatting"
            logger.info("[bot_tasks] %s: formatting with Claude...", task_id)
            formatted_text, inp_tok, out_tok, cost = await asyncio.to_thread(format_with_claude_sync, raw_text)
            logger.info(
                "[bot_tasks] %s: formatting done (%d chars)", task_id, len(formatted_text)
            )
            tasks_store[task_id]["status"] = "done"
            tasks_store[task_id]["transcription"] = formatted_text
            tasks_store[task_id]["claude_usage"] = {
                "input_tokens": inp_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
            }
        # === CHUNK ANALYSIS ===
        cut_min_val = 0
        if cut_minutes:
            try:
                cut_min_val = int(str(cut_minutes).replace("cut_", "").replace("no", "0"))
            except Exception:
                cut_min_val = 0

        if cut_min_val > 0 and fmt not in ("fmt_srt",):
            logger.info("[CHUNKS] %s: analyzing for %d min target", task_id, cut_min_val)
            tasks_store[task_id]["stage"] = "analyzing_chunks"

            video_duration = tasks_store[task_id].get("duration_seconds", len(raw_text) * 2)

            chunk_result = await asyncio.to_thread(
                analyze_chunks_with_claude,
                raw_text,
                cut_min_val,
                video_duration
            )

            if "error" not in chunk_result:
                tasks_store[task_id]["chunk_analysis"] = chunk_result
                warning_type = chunk_result.get("warning_type", "ok")
                if warning_type in ("loss", "surplus"):
                    tasks_store[task_id]["chunk_warning"] = {
                        "type": warning_type,
                        "message": chunk_result.get("warning_message", ""),
                        "kept_minutes": chunk_result.get("kept_minutes", cut_min_val),
                        "suggestion_minutes": chunk_result.get("suggestion_minutes", cut_min_val),
                    }

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

@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task_id in tasks_store:
        tasks_store[task_id]["status"] = "cancelled"
        return {"ok": True}
    return {"ok": False}

@router.get("/api/debug/logs")
async def get_debug_logs(n: int = 100):
    """Return last N log lines from in-memory buffer."""
    lines = list(_LOG_BUFFER)[-n:]
    return {"count": len(lines), "logs": lines}


@router.get("/api/debug/logs/clear")
async def clear_debug_logs():
    _LOG_BUFFER.clear()
    return {"cleared": True}
