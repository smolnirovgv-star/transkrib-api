"""Transcript view and export endpoints."""

import html as _html
import json
import urllib.parse
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..config import settings

router = APIRouter(prefix="/api/transcript", tags=["transcript"])

_DOUBLE = chr(9552) * 39
_SINGLE = chr(9472) * 39

_HTML_CSS = (
    "* { box-sizing: border-box; margin: 0; padding: 0; }"
    " body { font-family: system-ui, -apple-system, sans-serif;"
    "  background: #0F172A; color: #E2E8F0; padding: 2rem; }"
    " .page { max-width: 800px; margin: 0 auto; }"
    " .header { border-bottom: 2px solid #7C3AED;"
    "  padding-bottom: 1.5rem; margin-bottom: 2rem; }"
    " .title { font-size: 1.75rem; font-weight: 700;"
    "  color: #F8FAFC; margin-bottom: 0.75rem; }"
    " .meta { display: flex; flex-wrap: wrap; gap: 0.5rem; }"
    " .badge { display: inline-block; background: rgba(124,58,237,.13);"
    "  color: #A78BFA; border: 1px solid rgba(124,58,237,.3);"
    "  border-radius: 4px; padding: .25rem .75rem; font-size: .8rem; }"
    " .content { line-height: 1.85; }"
    " .para { display: flex; gap: 1.5rem; margin-bottom: 1.5rem;"
    "  align-items: flex-start; }"
    " .timecode { font-family: monospace; font-size: .75rem;"
    "  color: #7C3AED; background: rgba(124,58,237,.08);"
    "  border: 1px solid rgba(124,58,237,.25); border-radius: 4px;"
    "  padding: .2rem .5rem; white-space: nowrap;"
    "  margin-top: .25rem; flex-shrink: 0; }"
    " .para-text { font-size: 1rem; color: #CBD5E1; }"
    " .footer { margin-top: 3rem; padding-top: 1rem;"
    "  border-top: 1px solid #1E293B; font-size: .75rem;"
    "  color: #475569; text-align: center; }"
    " .print-btn { position: fixed; bottom: 2rem; right: 2rem;"
    "  background: #7C3AED; color: white; border: none;"
    "  border-radius: 8px; padding: .75rem 1.5rem; cursor: pointer;"
    "  font-size: .875rem; font-weight: 600;"
    "  box-shadow: 0 4px 12px rgba(124,58,237,.4); }"
    " .print-btn:hover { background: #6D28D9; }"
    " @media print { .print-btn { display: none; }"
    "  body { background: white; color: black; }"
    "  .timecode { color: #555; background: #f5f5f5; border-color: #ddd; }"
    "  .para-text { color: #222; } .title { color: #111; } }"
    " @media (max-width: 600px) { body { padding: 1rem; }"
    "  .para { flex-direction: column; gap: .5rem; } }"
)

_HTML_TEMPLATE = (
    "<!DOCTYPE html>"
    '<html lang="ru">'
    "<head>"
    '<meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    "<title>TITLE_PH</title>"
    "<style>CSS_PH</style>"
    "</head>"
    "<body>"
    '<div class="page">'
    '<div class="header">'
    '<div class="title">TITLE_PH</div>'
    '<div class="meta">'
    '<span class="badge">BADGE_DATE</span>'
    '<span class="badge">BADGE_DUR</span>'
    '<span class="badge">Transkrib SmartCut AI</span>'
    "</div></div>"
    '<div class="content">PARAGRAPHS_PH</div>'
    '<div class="footer">&copy; Transkrib SmartCut AI | transkrib.ai</div>'
    "</div>"
    '<button class="print-btn" onclick="window.print()">&#128424; \u041f\u0435\u0447\u0430\u0442\u044c</button>'
    "</body></html>"
)


def _get_segments(stem: str) -> list[dict]:
    seg_path = settings.result_dir / f"{stem}_segments.json"
    if not seg_path.exists():
        txt_path = settings.result_dir / f"{stem}_transcript.txt"
        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8")
            return [
                {"text": line, "start": 0.0, "end": 0.0, "pause_before": 0.0, "score": 5, "reason": ""}
                for line in text.splitlines() if line.strip()
            ]
        return []
    return json.loads(seg_path.read_text(encoding="utf-8"))


def _to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _tc(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _duration_str(segments: list[dict]) -> str:
    if not segments:
        return "0:00"
    total = max(s.get("end", 0.0) for s in segments)
    return _tc(total)


def _raw_text(segments: list[dict]) -> str:
    return chr(10).join(s["text"] for s in segments if s.get("text"))


def _get_formatted_text(stem: str, segments: list[dict]) -> str:
    from app.services.transcript_formatter import format_transcript
    cache_path = settings.result_dir / f"{stem}_formatted.txt"
    raw = _raw_text(segments)
    return format_transcript(
        text=raw,
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
        cache_path=cache_path,
    )


def _format_srt(segments: list[dict]) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        start = _to_srt_time(s.get("start", 0))
        end = _to_srt_time(s.get("end", 0))
        lines.append(str(i) + chr(10) + start + " --> " + end + chr(10) + s["text"] + chr(10))
    return chr(10).join(lines)


def _format_txt(stem: str, segments: list[dict], formatted_text: str) -> str:
    seg_path = settings.result_dir / f"{stem}_segments.json"
    try:
        mtime = seg_path.stat().st_mtime
        date_str = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y")
    except Exception:
        date_str = datetime.now().strftime("%d.%m.%Y")
    duration = _duration_str(segments)
    title = stem.replace("_", " ").replace("-", " ")

    paragraphs = [p.strip() for p in formatted_text.split(chr(10) + chr(10)) if p.strip()]
    if not paragraphs:
        paragraphs = [formatted_text.strip()]

    hdr = [
        _DOUBLE,
        title,
        "\u0414\u0430\u0442\u0430: " + date_str + " | \u0414\u043b\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c: " + duration,
        "\u0422\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u043f\u0442 \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d: Transkrib SmartCut AI",
        _DOUBLE,
        "",
    ]
    ftr = [
        "",
        _SINGLE,
        "\u00a9 Transkrib SmartCut AI | transkrib.ai",
        _DOUBLE,
    ]
    return chr(10).join(hdr + paragraphs + ftr)


def _format_json(segments: list[dict], formatted_text: str) -> str:
    return json.dumps(
        {"formatted_text": formatted_text, "segments": segments},
        ensure_ascii=False,
        indent=2,
    )


def _format_html(stem: str, segments: list[dict], formatted_text: str) -> str:
    seg_path = settings.result_dir / f"{stem}_segments.json"
    try:
        mtime = seg_path.stat().st_mtime
        date_str = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y")
    except Exception:
        date_str = datetime.now().strftime("%d.%m.%Y")
    duration_str = _duration_str(segments)
    title = stem.replace("_", " ").replace("-", " ")

    paragraphs = [p.strip() for p in formatted_text.split(chr(10) + chr(10)) if p.strip()]
    if not paragraphs:
        paragraphs = [formatted_text.strip()]

    total_dur = max((s.get("end", 0.0) for s in segments), default=0.0)
    n = len(paragraphs)

    para_parts = []
    for i, para in enumerate(paragraphs):
        t = total_dur * i / n if n > 1 else 0.0
        tc = _tc(t)
        para_parts.append(
            '<div class="para">'
            + '<span class="timecode">[' + tc + ']</span>'
            + '<span class="para-text">' + _html.escape(para) + "</span>"
            + "</div>"
        )
    paragraphs_html = chr(10).join(para_parts)

    return (
        _HTML_TEMPLATE
        .replace("CSS_PH", _HTML_CSS)
        .replace("TITLE_PH", _html.escape(title))
        .replace("BADGE_DATE", "\U0001f4c5 " + _html.escape(date_str))
        .replace("BADGE_DUR", "\u23f1 " + _html.escape(duration_str))
        .replace("PARAGRAPHS_PH", paragraphs_html)
    )


@router.get('/{filename}/highlights')
def get_highlights(filename: str):
    stem = Path(filename).stem
    segments = _get_segments(stem)
    if not segments:
        raise HTTPException(404, 'No transcript found for: ' + filename)
    hi = [s for s in segments if s.get('score', 0) >= 6]
    if not hi:
        hi = segments[:10]
    return {'highlights': [{'text': s['text'], 'start': s.get('start', 0.0), 'score': s.get('score', 5)} for s in hi]}


@router.get("/{filename}")
def get_transcript(filename: str):
    stem = Path(filename).stem
    segments = _get_segments(stem)
    if not segments:
        raise HTTPException(404, f"No transcript found for: {filename}")
    formatted_text = _get_formatted_text(stem, segments)
    return {"segments": segments, "count": len(segments), "formatted_text": formatted_text}


@router.api_route("/{filename}/download", methods=["GET", "HEAD"])
def download_transcript(filename: str, format: str = "txt", request=None):
    stem = Path(filename).stem
    segments = _get_segments(stem)
    if not segments:
        raise HTTPException(404, f"No transcript found for: {filename}")

    fmt = format.lower()
    if fmt == "srt":
        content = _format_srt(segments)
        media_type = "text/plain"
        ext = "srt"
    elif fmt == "json":
        formatted_text = _get_formatted_text(stem, segments)
        content = _format_json(segments, formatted_text)
        media_type = "application/json"
        ext = "json"
    elif fmt == "html":
        formatted_text = _get_formatted_text(stem, segments)
        content = _format_html(stem, segments, formatted_text)
        media_type = "text/html"
        ext = "html"
    else:
        formatted_text = _get_formatted_text(stem, segments)
        content = _format_txt(stem, segments, formatted_text)
        media_type = "text/plain"
        ext = "txt"

    if request is not None and request.method == "HEAD":
        from starlette.responses import Response as _R
        return _R(status_code=200, headers={"Content-Type": media_type})
    safe_name = urllib.parse.quote((stem + '.' + ext).encode('utf-8'))
    cd = 'attachment; filename*=UTF-8' + chr(39) + chr(39) + safe_name
    return Response(
        content=content.encode('utf-8'),
        media_type=media_type,
        headers={'Content-Disposition': cd},
    )
