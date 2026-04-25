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
import traceback
import time
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
TMP_CACHE_TTL_SECONDS = 30 * 60  # 30 minutes for resize reuse
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


async def _tmp_cleanup_worker():
    """Background task: removes /tmp/{uuid}.mp4, .txt, _resized.mp4
    older than TMP_CACHE_TTL_SECONDS. Runs every 10 minutes."""
    import glob as _iglob
    while True:
        try:
            now = time.time()
            patterns = ["/tmp/*.mp4", "/tmp/*.txt", "/tmp/*_resized.mp4"]
            cleaned = 0
            for pattern in patterns:
                for path in _iglob.glob(pattern):
                    try:
                        age = now - os.path.getmtime(path)
                        if age > TMP_CACHE_TTL_SECONDS:
                            os.remove(path)
                            cleaned += 1
                    except (FileNotFoundError, PermissionError):
                        pass
            if cleaned > 0:
                logger.info("[tmp_cleanup] removed %d expired files", cleaned)
        except Exception as e:
            logger.warning("[tmp_cleanup] error: %s", e)
        await asyncio.sleep(600)


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

ФОРМАТ ВЫВОДА (ОБЯЗАТЕЛЬНО при транскрипции):

Разбей транскрипцию на смысловые разделы по темам. Для каждого раздела:
- Начни с заголовка на отдельной строке: <b>🎬 Название темы</b>
- Крупные подтемы выделяй как: <b>📌 Подтема</b>
- Текст разбивай на абзацы (двойной перенос строки между абзацами)
- Важные термины курсивом: <i>термин</i>
- Ключевые имена/даты/цифры жирным: <b>2026 год</b>

Допустимые HTML-теги: только <b>, <i>, <u>, <s>, <code>.
НЕ используй <h1>/<h2>/<h3>/<p>/<br>, markdown (**), и ** внутри тегов.
НЕ оборачивай весь текст в один <b>.

Пример правильной структуры:

<b>🎬 Вступление: знакомство с темой</b>

Автор объясняет, почему выбрана именно эта тема. Важный акцент на <i>практической применимости</i> идей.

<b>📌 Первая ключевая идея</b>

Раскрытие идеи с примерами. В <b>2026 году</b> статистика показала, что...

Второй абзац той же подтемы.

<b>🎬 Вторая большая тема</b>

...

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


def _is_formatter_refusal(data: dict, original_chunk: str) -> bool:
    """Return True if Claude refused to format (copyright/lyrics policy)."""
    # 1. Explicit refusal stop_reason (newer API versions)
    if data.get("stop_reason") == "refusal":
        return True
    # 2. Short response containing copyright refusal markers
    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    )
    text_lower = text.lower()
    refusal_markers = [
        "i cannot", "i can't", "i'm unable", "unable to",
        "copyright", "lyrics", "intellectual property",
        "я не могу", "не имею возможности",
    ]
    has_marker = any(m in text_lower for m in refusal_markers)
    if has_marker and len(text) < len(original_chunk) * 0.3:
        return True
    return False


async def format_transcription_with_claude(raw_text: str) -> tuple:
    """
    Async версия форматирования через Claude с поддержкой чанкинга до 30k симв.
    Возвращает (formatted_text, input_tokens, output_tokens, cost_usd).
    При любой ошибке фаллбэк: возвращает raw_text без изменений.
    """
    logger.info("[format_claude] called, text_len=%d", len(raw_text))
    api_key = os.environ.get("APP_ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[FORMAT] APP_ANTHROPIC_API_KEY not set, skipping formatting")
        return raw_text, 0, 0, 0.0

    CHUNK_SIZE = 30000
    if len(raw_text) <= CHUNK_SIZE:
        chunks = [raw_text]
    else:
        chunks = []
        remaining = raw_text
        while len(remaining) > CHUNK_SIZE:
            split_at = remaining.rfind('. ', 0, CHUNK_SIZE)
            if split_at == -1:
                split_at = CHUNK_SIZE
            else:
                split_at += 1
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            chunks.append(remaining)

    results = []
    total_inp = 0
    total_out = 0
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            for i, chunk in enumerate(chunks):
                logger.info("[FORMAT] chunk %d/%d (%d chars)", i + 1, len(chunks), len(chunk))
                logger.info(
                    "[format_claude] sending chunk %d/%d (%d chars) to Anthropic, timeout=180s",
                    i + 1, len(chunks), len(chunk)
                )
                resp = await asyncio.wait_for(
                    client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 8000,
                            "messages": [{
                                "role": "user",
                                "content": FORMATTING_PROMPT + "\n\n---\n\nОтформатируй транскрипцию согласно инструкциям:\n\n" + chunk,
                            }],
                        },
                    ),
                    timeout=180,
                )
                if resp.status_code != 200:
                    logger.error("[FORMAT] Claude error %d: %s", resp.status_code, resp.text[:300])
                    return raw_text, 0, 0, 0.0
                data = resp.json()
                if _is_formatter_refusal(data, chunk):
                    logger.warning(
                        "[FORMAT] chunk %d/%d: refusal detected, falling back to raw transcript",
                        i + 1, len(chunks)
                    )
                    raw_prefix = "⚠️ Без форматирования (защищённый контент). Сырой транскрипт ниже:\n\n"
                    return raw_prefix + raw_text, 0, 0, 0.0
                text = "".join(
                    b["text"] for b in data.get("content", []) if b.get("type") == "text"
                )
                usage = data.get("usage", {})
                total_inp += usage.get("input_tokens", 0)
                total_out += usage.get("output_tokens", 0)
                results.append(text.strip() if text.strip() else chunk)
        formatted = "\n\n".join(results)
        cost = (total_inp * 3.0 + total_out * 15.0) / 1_000_000
        logger.info("[FORMAT] done: %d chunk(s), %d chars, in=%d out=%d cost=$%.4f",
                    len(chunks), len(formatted), total_inp, total_out, cost)
        return formatted, total_inp, total_out, cost
    except asyncio.TimeoutError:
        logger.error("[format_claude] TIMEOUT after 60s, returning raw text")
        return raw_text, 0, 0, 0.0
    except Exception as e:
        logger.error("[format_claude] exception: %r", e, exc_info=True)
        return raw_text, 0, 0, 0.0


def _select_chunks_with_claude(
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


def _validate_chunk_for_ffmpeg(start_str, end_str):
    """Hard last-check before subprocess.run. Raises ValueError if interval is invalid."""
    def _parse(ts):
        parts = str(ts).replace(",", ".").split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(parts[0])
    s = _parse(start_str)
    e = _parse(end_str)
    if e <= s:
        raise ValueError(f"Invalid ffmpeg interval: ss={start_str} >= to={end_str}")
    if e <= 0 or s < 0:
        raise ValueError(f"Invalid ffmpeg timestamps: ss={start_str}, to={end_str}")


def cut_video_with_ffmpeg(
    video_path: str,
    chunks: list,
    output_path: str,
    task_id: str
) -> bool:
    """Нарезает видео по чанкам с include=True и склеивает в один файл."""
    import subprocess, os as _os

    included = [c for c in chunks if c.get("include", True)]
    if not included:
        logger.error("[CUT] %s: no chunks with include=True", task_id)
        return False

    logger.info("[CUT] %s: cutting %d/%d chunks", task_id, len(included), len(chunks))

    segment_paths = []
    concat_list_path = f"/tmp/{task_id}_concat.txt"

    try:
        for i, chunk in enumerate(included):
            # SRT timestamps use comma as decimal sep ("00:02:54,264") — ffmpeg needs dot
            start = str(chunk.get("start_time") or "00:00:00").replace(",", ".")
            end = str(chunk.get("end_time") or "00:00:00").replace(",", ".")
            seg_path = f"/tmp/{task_id}_seg{i}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", start,
                "-to", end,
                "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-avoid_negative_ts", "1",
                seg_path
            ]

            # Guard: ensure no SRT-style comma in any ffmpeg arg
            for _arg in cmd:
                if re.search(r'\d,\d', str(_arg)):
                    logger.error("[CUT] %s: SRT comma in ffmpeg arg %r — aborting seg %d", task_id, _arg, i)
                    continue

            # DBG-E: exact start/end strings going into guard and subprocess
            logger.info("[CUT] %s: DBG-E seg%d start=%r end=%r", task_id, i, start, end)
            # Hard guard: reject invalid ffmpeg intervals before subprocess
            try:
                _validate_chunk_for_ffmpeg(start, end)
            except ValueError as _e_guard:
                logger.error("[CUT] %s: ffmpeg guard rejected seg %d: %s", task_id, i, _e_guard)
                continue

            logger.info("[CUT] %s: seg%d cmd: %s", task_id, i, " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error("[CUT] ffmpeg seg %d failed: %s", i, result.stderr[-500:])
                continue

            if _os.path.exists(seg_path) and _os.path.getsize(seg_path) > 0:
                segment_paths.append(seg_path)
                logger.info("[CUT] seg %d: %s->%s (%.1f MB)", i, start, end,
                    _os.path.getsize(seg_path) / 1024 / 1024)

        if not segment_paths:
            logger.error("[CUT] %s: no segments created", task_id)
            return False

        with open(concat_list_path, "w") as f:
            for sp in segment_paths:
                f.write("file '" + sp + "'" + chr(10))

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        logger.info("[CUT] %s: concat cmd: %s", task_id, " ".join(cmd_concat))
        result = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error("[CUT] concat failed: %s", result.stderr[-200:])
            return False

        final_size = _os.path.getsize(output_path) / 1024 / 1024
        logger.info("[CUT] %s: done -> %s (%.1f MB)", task_id, output_path, final_size)
        logger.info("[CUT] final mp4 reencoded to H.264+AAC: %s (size=%s MB)",
                    output_path, round(_os.path.getsize(output_path) / 1024 / 1024, 1))
        return True

    except Exception as e:
        logger.exception("[CUT] %s: exception in cut_video_with_ffmpeg", task_id)
        return False
    finally:
        for sp in segment_paths:
            try: _os.remove(sp)
            except: pass
        try: _os.remove(concat_list_path)
        except: pass


def _ts_to_sec(t) -> float:
    """Parse 'HH:MM:SS[.mmm]' or plain float string to seconds."""
    t = str(t or "0").replace(",", ".")
    parts = t.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(t)


def _is_valid_chunks(chunks: list, duration: float) -> bool:
    """Check that Claude-selection returned a usable list of segments."""
    if not chunks or len(chunks) < 2:
        logger.debug("[CUT] _is_valid_chunks: rejected — count=%d < 2", len(chunks) if chunks else 0)
        return False
    for ch in chunks:
        try:
            start = _ts_to_sec(ch.get("start_time"))
            end = _ts_to_sec(ch.get("end_time"))
        except (ValueError, TypeError) as e:
            logger.debug("[CUT] _is_valid_chunks: parse error chunk=%s: %s", ch, e)
            return False
        reasons = []
        if start < 0:
            reasons.append(f"start<0 ({start})")
        if end <= 0:
            reasons.append(f"end<=0 ({end})")
        if start >= end:
            reasons.append(f"start>=end ({start}>={end})")
        if end - start < 1:
            reasons.append(f"duration<1s ({end - start:.2f}s)")
        if duration > 0 and end > duration + 1:
            reasons.append(f"end>duration+1 ({end}>{duration + 1})")
        if reasons:
            logger.debug("[CUT] _is_valid_chunks: chunk INVALID chunk=%s reasons=%s", ch, reasons)
            return False
        logger.debug("[CUT] _is_valid_chunks: chunk ok start=%.1f end=%.1f duration=%.1f", start, end, duration)
    return True


def _fmt_ts(s: float) -> str:
    s = int(s)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def generate_uniform_chunks(duration: float, cut_min_val: int) -> list:
    """N equal chunks of cut_min_val minutes, last one truncated.
    If duration is unknown (0), generates 3 chunks of cut_min_val minutes each
    without capping end time — produces valid non-zero intervals."""
    import math
    chunk_sec = cut_min_val * 60
    if duration > 0:
        n = math.ceil(duration / chunk_sec)
    else:
        # duration unknown — generate 3 full-length chunks, no end-capping
        n = 3
        duration = None  # signals: don't cap end
    result = []
    for i in range(n):
        start = i * chunk_sec
        end = start + chunk_sec if duration is None else min(start + chunk_sec, duration)
        result.append({
            "start_time": _fmt_ts(start),
            "end_time": _fmt_ts(end),
            "include": True,
        })
    return result


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


def _download_with_ytdlp(url: str, task_id: str, cookie_path: Optional[str] = None, video_needed: bool = False):
    """Level 1: yt-dlp download. video_needed=True скачивает видео+аудио для нарезки."""
    import glob
    import yt_dlp
    print(f"=== DOWNLOAD FUNCTION yt-dlp: {url} ===")
    logger.info("[bot_tasks] yt-dlp version: %s", yt_dlp.version.__version__)

    output_template = "/tmp/" + task_id + ".%(ext)s"

    if video_needed:
        ydl_opts = {
            "format": "best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "quiet": False,
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            "retries": 3,
            "socket_timeout": 30,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        }
    else:
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
    proxy_url = os.environ.get("YOUTUBE_PROXY", "") or os.environ.get("WEBSHARE_PROXY", "")
    if proxy_url:
        ydl_opts["proxy"] = proxy_url
        logger.info("[ytdlp] proxy enabled (source=%s)",
                    "YOUTUBE_PROXY" if os.environ.get("YOUTUBE_PROXY") else "WEBSHARE_PROXY")
    else:
        logger.warning("[ytdlp] NO proxy configured — YouTube likely to block")
    ydl_opts["extractor_args"] = {
        "youtube": {"player_client": ["ios", "web"]}
    }
    logger.info("[DOWNLOAD] Using format: %s", ydl_opts.get("format"))

    logger.info("[DOWNLOAD] Starting yt-dlp for: %s", url)
    logger.info("[DOWNLOAD] Output template: %s", output_template)

    # Log available formats before download
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl_info:
            info_only = ydl_info.extract_info(url, download=False)
            fmts = info_only.get("formats", []) if info_only else []
            fmt_summary = [(f.get("format_id"), f.get("ext"), f.get("height")) for f in fmts]
            logger.info("[DOWNLOAD] Available formats (%d): %s", len(fmt_summary), fmt_summary[:20])
    except Exception as e_fmt:
        logger.warning("[DOWNLOAD] Could not list formats: %s", e_fmt)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            logger.info("[DOWNLOAD] yt-dlp completed. Title: %s", info.get("title", "unknown"))
            logger.info("[DOWNLOAD] Format: %s, Ext: %s", info.get("format", "?"), info.get("ext", "?"))
    except Exception as e:
        err_str = str(e)
        logger.error("[DOWNLOAD] yt-dlp FAILED: %s: %s", type(e).__name__, e)
        if "format" in err_str.lower() or "not available" in err_str.lower():
            logger.info("[DOWNLOAD] Retrying without format selector...")
            ydl_opts_retry = {k: v for k, v in ydl_opts.items() if k != "format"}
            with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl2:
                info = ydl2.extract_info(url, download=True)
                logger.info("[DOWNLOAD] retry completed. Title: %s", info.get("title", "unknown"))
        else:
            logger.info("[DOWNLOAD] Retrying with OAuth2 (no proxy, no cookies)...")
            ydl_opts_oauth = {k: v for k, v in ydl_opts.items()
                              if k not in ("cookiefile", "proxy")}
            ydl_opts_oauth["username"] = "oauth2"
            ydl_opts_oauth["password"] = ""
            with yt_dlp.YoutubeDL(ydl_opts_oauth) as ydl_oauth:
                info = ydl_oauth.extract_info(url, download=True)
                logger.info("[DOWNLOAD] oauth2 retry completed. Title: %s", info.get("title", "unknown"))
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


def _download_video_cobalt(url: str, task_id: str):
    """
    Скачивает видео через cobalt.tools API.
    Возвращает путь к скачанному MP4 или None при ошибке.
    Cobalt.tools обходит YouTube IP-блокировки серверных IP.
    """
    import shutil
    output_path = f"/tmp/{task_id}_video.mp4"

    logger.info("[COBALT] %s: requesting video URL for: %s", task_id, url[:80])

    cobalt_url = os.getenv("COBALT_API_URL", "https://api.cobalt.tools/").rstrip("/") + "/"
    try:
        resp = requests.post(
            cobalt_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "videoQuality": "480",
                "downloadMode": "auto",
                "filenameStyle": "basic",
            },
            timeout=30,
        )
        logger.info("[cobalt] raw response: status=%s body=%s", resp.status_code, resp.text[:500])
        if resp.status_code != 200:
            logger.error("[COBALT] API error %d: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        status = data.get("status")
        logger.info("[COBALT] API status: %s", status)
        if status not in ("tunnel", "redirect", "stream"):
            logger.warning("[cobalt] no file in response: keys=%s status=%s", list(data.keys()), data.get("status"))
            logger.error("[COBALT] unexpected status: %s, data: %s", status, str(data)[:200])
            return None
        direct_url = data.get("url")
        if not direct_url:
            logger.error("[COBALT] no url in response: %s", str(data)[:200])
            return None
        logger.info("[COBALT] got direct URL, downloading...")
    except Exception as e:
        logger.error("[COBALT] API request failed: %s", e, exc_info=True)
        return None

    try:
        with requests.get(
            direct_url,
            stream=True,
            timeout=120,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True
        ) as r:
            if r.status_code != 200:
                logger.error("[COBALT] download failed: %d", r.status_code)
                return None
            total = 0
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        if total % (1024 * 1024) == 0:
                            logger.info("[COBALT] downloaded %.1f MB so far", total / 1024 / 1024)
        logger.info("[COBALT] downloaded %.1f MB", total / 1024 / 1024)
        if total < 10000:
            logger.error("[COBALT] file too small: %d bytes", total)
            return None
        return output_path
    except Exception as e:
        logger.error("[COBALT] download exception: %s", e, exc_info=True)
        if os.path.exists(output_path):
            os.remove(output_path)
        return None


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def _download_video_rapidapi(url: str, out_path: str, task_id: str) -> bool:
    """Download YouTube MP4 via RapidAPI YouTube Media Downloader (DataFanatic).
    Returns True on success, False otherwise."""
    if not RAPIDAPI_KEY:
        logger.warning("[rapidapi] RAPIDAPI_KEY not set, skipping")
        return False

    video_id = _extract_youtube_id(url)
    if not video_id:
        logger.warning("[rapidapi] failed to extract video_id from: %s", url)
        return False

    api_url = "https://youtube-media-downloader.p.rapidapi.com/v2/video/details"
    headers = {
        "x-rapidapi-host": "youtube-media-downloader.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    params = {
        "videoId": video_id,
        "urlAccess": "normal",
        "videos": "auto",
        "audios": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            logger.info("[rapidapi] requesting video details for: %s (videoId=%s)", url, video_id)
            resp = await client.get(api_url, headers=headers, params=params)

            if resp.status_code != 200:
                logger.warning("[rapidapi] status=%s body=%s",
                               resp.status_code, resp.text[:300])
                return False

            data = resp.json()

            if data.get("errorId") != "Success":
                logger.warning("[rapidapi] errorId=%s", data.get("errorId"))
                return False

            items = data.get("videos", {}).get("items", [])
            if not items:
                logger.warning("[rapidapi] no video items in response")
                return False

            mp4_with_audio = [i for i in items if i.get("extension") == "mp4" and i.get("hasAudio") is True]

            if not mp4_with_audio:
                logger.warning("[rapidapi] no mp4 with audio found")
                return False

            quality_priority = {"720p": 1, "480p": 2, "360p": 3, "240p": 4, "144p": 5}
            best = sorted(
                [i for i in mp4_with_audio if i.get("height", 0) <= 720],
                key=lambda x: (quality_priority.get(x.get("quality"), 99), -x.get("height", 0))
            )

            if not best:
                best = mp4_with_audio

            chosen = best[0]
            video_url = chosen.get("url")
            quality = chosen.get("quality", "unknown")
            size_mb = round(chosen.get("size", 0) / 1024 / 1024, 1)

            if not video_url:
                logger.warning("[rapidapi] chosen item has no URL")
                return False

            logger.info("[rapidapi] downloading %s (%s MB)...", quality, size_mb)

            async with client.stream("GET", video_url) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    async for chunk in r.aiter_bytes(8192):
                        f.write(chunk)

            actual_mb = round(os.path.getsize(out_path) / 1024 / 1024, 1)
            logger.info("[rapidapi] downloaded %s MB to %s", actual_mb, out_path)
            return True

    except Exception as e:
        logger.warning("[rapidapi] failed: %s", str(e)[:200], exc_info=True)
        return False


_YTDLP_COOKIES_PATH = None


def _prepare_ytdlp_cookies() -> Optional[str]:
    global _YTDLP_COOKIES_PATH
    if _YTDLP_COOKIES_PATH and os.path.exists(_YTDLP_COOKIES_PATH):
        return _YTDLP_COOKIES_PATH
    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if not b64:
        logger.warning("YOUTUBE_COOKIES_B64 is empty — yt-dlp will run without cookies")
        return None
    try:
        import base64 as _b64
        raw = _b64.b64decode(b64)
        import tempfile as _tf
        p = os.path.join(_tf.gettempdir(), "youtube_cookies.txt")
        with open(p, "wb") as f:
            f.write(raw)
        _YTDLP_COOKIES_PATH = p
        logger.info("yt-dlp cookies prepared at %s (%d bytes)", p, len(raw))
        return p
    except Exception as e:
        logger.error("Failed to prepare yt-dlp cookies: %r", e)
        return None


def _download_video_pytubefix(url: str, out_path: str) -> None:
    """Download YouTube video via pytubefix (no cookies, no proxy)."""
    from pytubefix import YouTube
    logger.info("[pytubefix] requesting: %s", url)
    proxy_url = os.environ.get(
        "WEBSHARE_PROXY",
        "http://tnylobxq-rotate:8hj6ju41jo98@p.webshare.io:80/"
    )
    proxies = {"http": proxy_url, "https": proxy_url}
    masked = proxy_url.split("@")[1] if "@" in proxy_url else "no-auth"
    logger.info("[pytubefix] using proxy: %s", masked)
    yt = YouTube(url, proxies=proxies)
    logger.info("[pytubefix] YouTube object created")
    stream = (
        yt.streams
          .filter(progressive=True, file_extension="mp4")
          .order_by("resolution")
          .desc()
          .first()
    )
    if stream is None:
        stream = (
            yt.streams
              .filter(file_extension="mp4")
              .order_by("resolution")
              .desc()
              .first()
        )
    if stream is None:
        raise RuntimeError("pytubefix: no suitable stream found")
    logger.info("[pytubefix] stream: itag=%s res=%s size=%s",
                stream.itag, stream.resolution, stream.filesize)
    out_dir = os.path.dirname(out_path) or "."
    out_name = os.path.basename(out_path)
    stream.download(output_path=out_dir, filename=out_name)
    logger.info("[pytubefix] downloaded to %s", out_path)

async def _download_video_supadata(url: str, out_path: str, task_id: str) -> bool:
    """Level 0 fallback: Supadata.ai YouTube downloader.
    Returns True on success, False otherwise."""
    if not SUPADATA_API_KEY:
        logger.warning("[supadata] SUPADATA_API_KEY not set, skipping")
        return False

    api_url = "https://api.supadata.ai/v1/youtube/video"
    headers = {"x-api-key": SUPADATA_API_KEY}
    params = {"url": url, "format": "mp4"}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            logger.info("[supadata] requesting MP4 for: %s", url)
            resp = await client.get(api_url, headers=headers, params=params)

            if resp.status_code != 200:
                logger.warning("[supadata] status=%s body=%s",
                               resp.status_code, resp.text[:300])
                return False

            data = resp.json()
            video_url = data.get("video_url") or data.get("url") or data.get("download_url")
            if not video_url:
                logger.warning("[supadata] no video_url in response: %s",
                               str(data)[:300])
                return False

            logger.info("[supadata] got video_url, downloading...")
            async with client.stream("GET", video_url) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    async for chunk in r.aiter_bytes(8192):
                        f.write(chunk)

            size_mb = round(os.path.getsize(out_path) / 1024 / 1024, 1)
            logger.info("[supadata] downloaded %s MB to %s", size_mb, out_path)
            return True

    except Exception as e:
        logger.warning("[supadata] failed: %s", str(e)[:200])
        return False

async def download_youtube(url: str, task_id: str, out_path: str) -> dict:
    """
    Tries to download a YouTube video via fallback chain.
    Returns {"ok": True, "method": "ytdlp|cobalt|rapidapi", "path": out_path}
    or {"ok": False, "error": "..."} if all levels fail.
    """
    import glob as _glob
    errors = []

    # Level 0: Supadata (professional YouTube downloader)
    logger.info("download_youtube: trying supadata (Level 0)")
    if await _download_video_supadata(url, out_path, task_id):
        return {"ok": True, "method": "supadata", "path": out_path}

    # Level 1: pytubefix (не требует cookies)
    try:
        logger.info("download_youtube: trying pytubefix")
        await asyncio.wait_for(
            asyncio.to_thread(_download_video_pytubefix, url, out_path),
            timeout=120
        )
        logger.info("download_youtube: pytubefix OK")
        return {"ok": True, "method": "pytubefix", "path": out_path}
    except asyncio.TimeoutError:
        logger.warning("[download_youtube] pytubefix timeout after 120s, moving to next fallback")
        errors.append("pytubefix: timeout 120s")
    except Exception as e:
        logger.warning("download_youtube: pytubefix failed: %r", e)
        errors.append(f"pytubefix: {e}")

    # Level 1: yt-dlp (with Webshare proxy + cookies)
    try:
        logger.info("download_youtube: trying yt-dlp")
        cookies_file_v = _prepare_ytdlp_cookies() or _get_cookie_file()
        logger.info("[download_youtube] yt-dlp format: best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best")
        tmp_id = task_id + "_ytdl"
        await asyncio.wait_for(
            asyncio.to_thread(_download_with_ytdlp, url, tmp_id, cookies_file_v, True),
            timeout=DOWNLOAD_TIMEOUT
        )
        video_files = _glob.glob(f"/tmp/{tmp_id}.*")
        if video_files:
            import shutil as _shutil
            _shutil.move(video_files[0], out_path)
            logger.info("download_youtube: yt-dlp OK")
            return {"ok": True, "method": "ytdlp", "path": out_path}
        errors.append("ytdlp: no file produced")
    except Exception as e:
        logger.warning("download_youtube: yt-dlp failed: %r", e)
        errors.append(f"ytdlp: {e}")

    # Level 1: cobalt.tools
    try:
        logger.info("download_youtube: trying cobalt")
        cobalt_path = await asyncio.to_thread(_download_video_cobalt, url, task_id)
        if cobalt_path and os.path.exists(cobalt_path):
            if cobalt_path != out_path:
                import shutil as _shutil
                _shutil.move(cobalt_path, out_path)
            logger.info("download_youtube: cobalt OK")
            return {"ok": True, "method": "cobalt", "path": out_path}
        errors.append("cobalt: no file returned")
    except Exception as e:
        logger.warning("download_youtube: cobalt failed: %r", e)
        errors.append(f"cobalt: {e}")

    # Level 2: RapidAPI
    try:
        logger.info("download_youtube: trying rapidapi")
        if await _download_video_rapidapi(url, out_path, task_id):
            logger.info("download_youtube: rapidapi OK")
            return {"ok": True, "method": "rapidapi", "path": out_path}
        errors.append("rapidapi: no file returned")
    except Exception as e:
        logger.warning("download_youtube: rapidapi failed: %r", e)
        errors.append(f"rapidapi: {e}")

    return {"ok": False, "error": " | ".join(errors)}

async def _download_video_savefrom(task_id: str, url: str, output_path: str) -> bool:
    """Level 2 fallback: SaveFrom.net API"""
    try:
        import requests as _req
        video_id = url.split("v=")[-1].split("&")[0]

        # SaveFrom hidden API
        api_url = f"https://worker.sf-tools.com/savefrom.net/api/convert"
        resp = _req.get(api_url,
            params={"url": url, "lang": "en"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=20
        )
        logger.info("[SAVEFROM] status: %s", resp.status_code)

        if resp.status_code != 200:
            logger.error("[SAVEFROM] error %s", resp.status_code)
            return False

        data = resp.json()
        logger.info("[SAVEFROM] response keys: %s", list(data.keys())[:5])

        # Find MP4 download URL
        mp4_url = None
        urls = data.get("url", [])
        if isinstance(urls, list):
            for item in urls:
                if "mp4" in item.get("type", "").lower() or "mp4" in item.get("ext", "").lower():
                    mp4_url = item.get("url") or item.get("link")
                    break
        elif isinstance(urls, str):
            mp4_url = urls

        if not mp4_url:
            logger.error("[SAVEFROM] no mp4 url found, data: %s", str(data)[:200])
            return False

        logger.info("[SAVEFROM] got mp4 url, downloading...")
        vid_resp = _req.get(mp4_url, stream=True, timeout=120,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True
        )
        total = 0
        with open(output_path, "wb") as f:
            for chunk in vid_resp.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)
        logger.info("[SAVEFROM] downloaded %.1f MB", total/1024/1024)
        return total > 10000
    except Exception as e:
        logger.error("[SAVEFROM] exception: %s", str(e)[:100])
        return False



async def _download_video_turboscribe(task_id: str, url: str, output_path: str) -> bool:
    """Level 2b fallback: TurboScribe downloader page"""
    try:
        import requests as _req
        import re as _re
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        # Step 1: GET downloader page, find dynamic htmx endpoint
        page_resp = _req.get(
            "https://turboscribe.ai/downloader/youtube/mp4",
            headers={"User-Agent": ua},
            timeout=20
        )
        logger.info("[TURBOSCRIBE] page status: %s", page_resp.status_code)
        if page_resp.status_code != 200:
            logger.error("[TURBOSCRIBE] page load failed: %s", page_resp.status_code)
            return False
        m_form = _re.search(r'hx-post="(/_htmx/[^"]+)"', page_resp.text)
        if not m_form:
            logger.error("[TURBOSCRIBE] htmx endpoint not found in page")
            return False
        htmx_path = m_form.group(1)
        logger.info("[TURBOSCRIBE] htmx endpoint: %s", htmx_path)
        # Step 2: POST to dynamic endpoint
        resp2 = _req.post(
            f"https://turboscribe.ai{htmx_path}",
            data={"url": url},
            headers={"User-Agent": ua},
            timeout=30
        )
        logger.info("[TURBOSCRIBE] htmx status: %s", resp2.status_code)
        logger.info("[TURBOSCRIBE] htmx response: %s", resp2.text[:300])
        # Step 3: find googlevideo / videoplayback URL
        mp4_url = None
        if resp2.status_code == 200:
            m_url = _re.search(r'href="(https?://[^"]*(?:googlevideo|videoplayback)[^"]*)"', resp2.text)
            if m_url:
                mp4_url = m_url.group(1)
        if not mp4_url:
            logger.error("[TURBOSCRIBE] no video url found")
            return False
        logger.info("[TURBOSCRIBE] got video url, downloading...")
        vid_resp = _req.get(mp4_url, stream=True, timeout=120,
            headers={"User-Agent": ua},
            allow_redirects=True
        )
        total = 0
        with open(output_path, "wb") as f:
            for chunk in vid_resp.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)
        logger.info("[TURBOSCRIBE] downloaded %.1f MB", total/1024/1024)
        return total > 10000
    except Exception as e:
        logger.error("[TURBOSCRIBE] exception: %s", str(e)[:100])
        return False

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
    import time as _t_mod
    from app.services.metrics import record_task_metric
    _m_start = _t_mod.time()
    _m_dl = None   # download_method
    _m_cut = None  # cut_status
    _m_fmt = None  # formatter_status
    _m_final = "unknown"
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
            task_id, fmt, "srt" if fmt in ("fmt_srt", "fmt_cut_srt") else "text")
        output_format = "srt" if fmt in ("fmt_srt", "fmt_cut_srt") else "text"  # fmt_md treated as text

        # Check video duration before processing
        try:
            import yt_dlp as ytdlp
            _dur_cookies = _get_cookie_file()
            _dur_opts = {"quiet": True, "skip_download": True}
            if _dur_cookies:
                _dur_opts["cookiefile"] = _dur_cookies
            with ytdlp.YoutubeDL(_dur_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get("duration", 0) or 0
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
        if is_supadata_supported and os.getenv("SUPADATA_API_KEY") and not raw_text and fmt not in ("fmt_srt", "fmt_cut_srt"):
            try:
                logger.info("[SUPADATA] %s: trying Supadata for: %s", task_id, url)
                raw_text = await asyncio.to_thread(_get_transcript_supadata, url)
                logger.info("[SUPADATA] %s: SUCCESS! Got %d chars", task_id, len(raw_text))
                _m_dl = "supadata"
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
                _m_dl = "supadata"  # transcript via API
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

            download_result = None
            ytdlp_error = None

            # Level 1: yt-dlp (всегда пробуем первым — быстрее для Rutube/VK)
            try:
                download_result = await asyncio.wait_for(
                    asyncio.to_thread(_download_with_ytdlp, url, task_id, cookies_file),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                logger.info("[bot_tasks] %s: yt-dlp OK", task_id)
                _m_dl = "yt_dlp"
            except Exception as e1:
                ytdlp_error = e1
                logger.warning("[bot_tasks] %s: yt-dlp failed: %s", task_id, e1)
                tasks_store[task_id]["debug_log"] = f"yt-dlp FAILED: {str(e1)[:200]}"

            # Level 2+: download_youtube fallback (только для YouTube)
            if not download_result and is_youtube:
                audio_path = f"/tmp/{task_id}.mp3"
                tmp_mp4 = f"/tmp/{task_id}_fallback.mp4"
                logger.info("[bot_tasks] %s: yt-dlp failed, trying download_youtube fallback...", task_id)
                tasks_store[task_id]["debug_log"] = "trying download_youtube fallback..."
                dl_result = await download_youtube(url, task_id, tmp_mp4)
                if dl_result["ok"]:
                    mp4_path = dl_result["path"]
                    logger.info("[bot_tasks] %s: download_youtube OK via %s", task_id, dl_result["method"])
                    _m_dl = dl_result.get("method", "yt_dlp")
                    # Extract audio from mp4 via ffmpeg
                    try:
                        import subprocess
                        result = subprocess.run(
                            ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "libmp3lame",
                             "-b:a", "128k", "-ar", "16000", "-ac", "1", audio_path],
                            capture_output=True, text=True, timeout=180
                        )
                        if result.returncode == 0 and os.path.exists(audio_path):
                            download_result = audio_path
                            logger.info("[bot_tasks] %s: audio extracted OK via %s", task_id, dl_result["method"])
                            tasks_store[task_id]["debug_log"] = f"fallback: {dl_result['method']} + ffmpeg OK"
                        else:
                            logger.error("[bot_tasks] %s: ffmpeg failed: %s", task_id, result.stderr[:300])
                        standard_mp4 = f"/tmp/{task_id}.mp4"
                        try:
                            if mp4_path != standard_mp4:
                                os.rename(mp4_path, standard_mp4)
                            logger.info("[REUSE] keeping mp4 for CUT stage: %s", standard_mp4)
                        except Exception as e_mv:
                            logger.warning("[REUSE] failed to keep mp4: %s", e_mv)
                            try: os.remove(mp4_path)
                            except: pass
                    except Exception as e_ff:
                        logger.error("[bot_tasks] %s: ffmpeg exception: %s", task_id, e_ff)
                else:
                    logger.error("[bot_tasks] %s: download_youtube failed: %s", task_id, dl_result["error"])

            # Если ничего не помогло — человечное сообщение
            if not download_result:
                _m_dl = "all_failed"
                _m_final = "download_failed"
                logger.error("[bot_tasks] %s: all download methods failed", task_id)
                if is_youtube:
                    raise Exception(
                        "Не удалось скачать YouTube-видео. "
                        "Попробованы: yt-dlp, cobalt, rapidapi. "
                        "Попробуйте другое видео или пришлите ссылку ещё раз."
                    )
                if ytdlp_error:
                    raise ytdlp_error
                raise Exception("All download methods failed")

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
            _m_fmt = "not_requested"
            tasks_store[task_id]["transcription"] = raw_text
        else:
            # Убираем артефакты Whisper ">>" (маркер смены говорящего)
            raw_text = raw_text.replace(">>", "").strip()
            raw_text = " ".join(raw_text.split())
            tasks_store[task_id]["stage"] = "formatting"
            logger.info("[bot_tasks] %s: formatting with Claude...", task_id)
            formatted_text, inp_tok, out_tok, cost = await format_transcription_with_claude(raw_text)
            # Track formatter status
            if inp_tok > 0 or out_tok > 0:
                _m_fmt = "success"
            elif "⚠" in formatted_text[:5]:  # copyright fallback prefix
                _m_fmt = "copyright_fallback"
            else:
                _m_fmt = "error"
            logger.info(
                "[bot_tasks] %s: formatting done (%d chars)", task_id, len(formatted_text)
            )
            tasks_store[task_id]["transcription"] = formatted_text
            tasks_store[task_id]["claude_usage"] = {
                "input_tokens": inp_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
            }
        # Save raw transcript for resize reuse
        if raw_text:
            transcript_path = f"/tmp/{task_id}.txt"
            try:
                with open(transcript_path, "w", encoding="utf-8") as _tf:
                    _tf.write(raw_text)
                logger.info("[CACHE] saved transcript to %s (%d chars)", transcript_path, len(raw_text))
            except Exception as e_cache:
                logger.warning("[CACHE] failed to save transcript: %s", e_cache)

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
                _select_chunks_with_claude,
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

        # === VIDEO CUTTING ===
        logger.info("[CUT_ENTRY] task=%s cut_min_val=%d fmt=%r output_format=%r",
                    task_id, cut_min_val, fmt, output_format)
        if cut_min_val > 0:
            tasks_store[task_id]["status"] = "cutting"
            tasks_store[task_id]["progress"] = 4
            chunk_result = tasks_store[task_id].get("chunk_analysis", {})
            chunks = chunk_result.get("chunks", [])
            logger.info("[CUT] %s: chunks=%d chunk_analysis_present=%s",
                        task_id, len(chunks), bool(chunk_result))
            # DBG-A: raw chunks from Claude
            logger.info("[CUT] %s: DBG-A raw_chunks=%s", task_id, chunks[:3])

            # Uniform-cut fallback: если Claude вернул невалидные сегменты
            _duration = tasks_store[task_id].get("duration_seconds", 0)
            # DBG-B: before validator
            logger.info("[CUT] %s: DBG-B before_validator chunks=%s duration=%s", task_id, chunks[:3], _duration)
            _chunks_valid = _is_valid_chunks(chunks, _duration)
            # DBG-C: validator result
            logger.info("[CUT] %s: DBG-C validator_result=%s", task_id, _chunks_valid)
            _m_cut = "success" if _chunks_valid else None
            if not _chunks_valid:
                logger.info("[CUT] %s: validator REJECTED chunks (count=%d), examples: %s",
                            task_id, len(chunks) if chunks else 0, chunks[:3])
                logger.info("[CUT] %s: uniform-cut fallback STARTED, generating chunks for duration=%s, cut_min_val=%s",
                            task_id, _duration, cut_min_val)
                chunks = generate_uniform_chunks(_duration, cut_min_val)
                logger.info("[CUT] %s: uniform-cut chunks generated: %s", task_id, chunks)
                _m_cut = "uniform_fallback"

            # Если нет chunks из анализа — нарезка по равным интервалам
            if not chunks:
                duration_sec = cut_min_val * 60
                chunks = [
                    {"start_time": f"{(i * cut_min_val) // 60:02d}:{(i * cut_min_val) % 60:02d}:00",
                     "end_time":   f"{((i+1) * cut_min_val) // 60:02d}:{((i+1) * cut_min_val) % 60:02d}:00",
                     "include": True}
                    for i in range(3)
                ]
                logger.info("[CUT] %s: equal-interval fallback chunks (%d min each)", task_id, cut_min_val)

            tasks_store[task_id]["stage"] = "cutting_video"
            logger.info("[CUT] %s: starting video cut", task_id)

            video_path = f"/tmp/{task_id}.mp4"

            if os.path.exists(video_path):
                logger.info("[CUT] REUSING existing mp4: %s", video_path)
            else:
                logger.info("[CUT] %s: mp4 not found, downloading for cutting...", task_id)
                video_path = None

                is_youtube_cut = "youtube.com" in url or "youtu.be" in url
                logger.info("[CUT] %s: is_youtube_cut=%s url=%s",
                            task_id, is_youtube_cut, url[:60])

                if is_youtube_cut:
                    tmp_video = f"/tmp/{task_id}.mp4"
                    dl_result = await download_youtube(
                        tasks_store[task_id].get("url", url), task_id, tmp_video
                    )
                    if dl_result["ok"]:
                        video_path = tmp_video
                        logger.info("[CUT] %s: downloaded via %s", task_id, dl_result["method"])
                    else:
                        logger.error("[CUT] %s: all YouTube download methods failed: %s",
                                     task_id, dl_result["error"])
                        tasks_store[task_id]["cut_download_warning"] = (
                            "⚠️ Транскрипция готова, но нарезанное видео не удалось скачать. "
                            "Попробуйте другое видео или режим 'Только транскрипция'."
                        )
                else:
                    # Non-YouTube (Rutube, VK etc.): yt-dlp only
                    logger.info("[CUT] %s: trying yt-dlp for non-YouTube...", task_id)
                    try:
                        cookies_file_v = _get_cookie_file()
                        await asyncio.wait_for(
                            asyncio.to_thread(
                                _download_with_ytdlp,
                                tasks_store[task_id].get("url", url),
                                task_id + "_video",
                                cookies_file_v,
                                True
                            ),
                            timeout=DOWNLOAD_TIMEOUT
                        )
                        import glob as _glob
                        video_files = _glob.glob(f"/tmp/{task_id}_video.*")
                        if video_files:
                            video_path = video_files[0]
                            logger.info("[CUT] %s: yt-dlp success: %s", task_id, video_path)
                        else:
                            logger.warning("[CUT] %s: yt-dlp returned no file", task_id)
                    except Exception as e_v:
                        logger.error("[CUT] %s: yt-dlp exception: %s", task_id,
                                     traceback.format_exc())

                logger.info("[CUT] %s: video_path after download=%s", task_id, video_path)
                if not video_path:
                    logger.error("[CUT] %s: all download methods failed, skipping cut", task_id)

            # Конвертировать в MP4 если нужно
            if video_path and not video_path.endswith(".mp4"):
                logger.info("[CUT] %s: converting to MP4...", task_id)
                mp4_path = f"/tmp/{task_id}_video.mp4"
                try:
                    import subprocess as _sp
                    result = _sp.run([
                        "ffmpeg", "-y", "-i", video_path,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                        "-c:a", "aac", "-b:a", "128k",
                        mp4_path
                    ], capture_output=True, text=True, timeout=300)
                    if result.returncode == 0:
                        os.remove(video_path)
                        video_path = mp4_path
                        logger.info("[CUT] %s: converted to MP4", task_id)
                    else:
                        logger.warning("[CUT] %s: MP4 conversion failed, using original", task_id)
                except Exception as e_conv:
                    logger.warning("[CUT] %s: conversion error: %s", task_id, e_conv)

            if video_path and os.path.exists(video_path):
                output_video = f"/tmp/{task_id}_cut.mp4"
                # DBG-D: chunks entering cut_video_with_ffmpeg
                logger.info("[CUT] %s: DBG-D pre_ffmpeg chunks=%s", task_id, chunks[:3])
                success = await asyncio.to_thread(
                    cut_video_with_ffmpeg,
                    video_path,
                    chunks,
                    output_video,
                    task_id
                )
                if success:
                    tasks_store[task_id]["output_video_path"] = output_video
                    logger.info("[CUT] %s: video ready at %s", task_id, output_video)
                else:
                    logger.error("[CUT] %s: video cutting failed", task_id)
                    _m_cut = "failed"
                    tasks_store[task_id]["cut_error"] = (
                        "⚠️ Не удалось нарезать видео. Транскрипт/SRT выше готовы. "
                        "Попробуйте ещё раз или пришлите другой URL."
                    )

                try: os.remove(video_path)
                except: pass

        _m_final = "success"
        tasks_store[task_id]["status"] = "done"

    except asyncio.TimeoutError:
        _m_final = "download_failed"
        logger.error("[bot_tasks] %s: TIMEOUT during download", task_id)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = "Timeout: download took too long"
    except Exception as e:
        logger.error("[bot_tasks] %s: error - %s", task_id, e, exc_info=True)
        tasks_store[task_id]["status"] = "error"
        tasks_store[task_id]["error"] = str(e)[:500]
    finally:
        # Record metrics to Supabase task_metrics (defensive)
        try:
            record_task_metric(
                task_id=task_id,
                final_status=_m_final,
                cut_status=_m_cut,
                download_method=_m_dl,
                formatter_status=_m_fmt,
                processing_time_sec=int(_t_mod.time() - _m_start),
            )
        except Exception:
            pass  # double safety guard
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

@router.get("/api/tasks/{task_id}/video")
async def download_video(task_id: str):
    """Скачать нарезанное видео."""
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    if task_id not in tasks_store:
        raise HTTPException(404, "Task not found")
    video_path = tasks_store[task_id].get("output_video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(404, "Video not ready")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"transkrib_{task_id[:8]}.mp4"
    )



@router.post("/api/tasks/{task_id}/resize")
async def resize_task(task_id: str, target_minutes: float):
    """Reuse cached MP4+transcript to re-cut with new target duration."""
    from fastapi import HTTPException
    mp4_path = f"/tmp/{task_id}.mp4"
    transcript_path = f"/tmp/{task_id}.txt"

    if not os.path.exists(mp4_path) or not os.path.exists(transcript_path):
        raise HTTPException(404, "Cached files not found — please re-send the link")

    with open(transcript_path, encoding="utf-8") as _f:
        transcript = _f.read()

    logger.info("[RESIZE] task=%s target=%.1f min", task_id, target_minutes)

    video_duration = len(transcript) * 2  # rough estimate
    chunk_result = await asyncio.to_thread(
        _select_chunks_with_claude, transcript, target_minutes, video_duration
    )
    if "error" in chunk_result:
        raise HTTPException(500, f"Claude error: {chunk_result['error']}")

    chunks = chunk_result.get("chunks", [])
    logger.info("[RESIZE] selected %d chunks", len(chunks))

    output_path = f"/tmp/{task_id}_resized.mp4"
    ok = await asyncio.to_thread(
        cut_video_with_ffmpeg, mp4_path, chunks, output_path, task_id
    )
    if not ok or not os.path.exists(output_path):
        raise HTTPException(500, "ffmpeg failed to produce resized video")

    size_mb = round(os.path.getsize(output_path) / 1024 / 1024, 1)
    logger.info("[RESIZE] done: %s (%s MB)", output_path, size_mb)
    return {"ok": True, "path": output_path, "size_mb": size_mb}


@router.get("/api/tasks/{task_id}/resized_video")
async def get_resized_video(task_id: str):
    """Serve the resized video file."""
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    path = f"/tmp/{task_id}_resized.mp4"
    if not os.path.exists(path):
        raise HTTPException(404, "Resized video not found")
    return FileResponse(path, media_type="video/mp4", filename=f"resized_{task_id[:8]}.mp4")


@router.get("/api/debug/logs")
async def get_debug_logs(n: int = 100):
    """Return last N log lines from in-memory buffer."""
    lines = list(_LOG_BUFFER)[-n:]
    return {"count": len(lines), "logs": lines}


@router.get("/api/debug/logs/clear")
async def clear_debug_logs():
    _LOG_BUFFER.clear()
    return {"cleared": True}
