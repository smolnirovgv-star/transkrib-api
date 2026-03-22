"""Export endpoint: re-encode result video with custom quality/format/resolution."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..services.ffmpeg_service import FFmpegService

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    source_filename: str
    output_path: str
    format: str = "mp4"          # mp4 | mkv | webm
    crf: int = 23                 # 18 | 23 | 28
    resolution: str = "original" # original | 1080p | 720p | 480p
    subtitle_mode: str = "none"  # embed | srt | both | none


def _scale_filter(resolution: str) -> list[str]:
    mapping = {"1080p": "1080", "720p": "720", "480p": "480"}
    h = mapping.get(resolution)
    if not h:
        return []
    return ["-vf", f"scale=-2:{h}"]


def _video_codec_args(fmt: str, crf: int) -> list[str]:
    if fmt == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]


@router.post("/")
async def export_video(req: ExportRequest):
    """Re-encode a result video with specified quality/format/resolution."""
    src = settings.result_dir / req.source_filename
    if not src.exists():
        import os as _os
        appdata = _os.environ.get('APPDATA', '')
        candidates = [
            Path(appdata) / 'Transkrib' / 'storage' / 'results' / req.source_filename,
            Path(_os.path.dirname(_os.path.abspath(__file__))) / '..' / '..' / 'storage' / 'results' / req.source_filename,
            Path('storage') / 'results' / req.source_filename,
        ]
        found = next((p for p in candidates if p.exists()), None)
        if found:
            src = found
        else:
            raise HTTPException(404, {'error': 'Файл не найден: ' + req.source_filename + '. Проверьте что видео ещё не удалено.'})

    out = Path(req.output_path)
    if not out.parent.exists():
        raise HTTPException(400, f"Output directory does not exist: {out.parent}")

    ffmpeg = FFmpegService(settings.ffmpeg_path)

    cmd = [ffmpeg.ffmpeg_path, "-i", str(src)]
    cmd += _scale_filter(req.resolution)
    cmd += _video_codec_args(req.format, req.crf)

    if req.format == "webm":
        cmd += ["-c:a", "libopus", "-b:a", "128k"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    # Look for matching .srt in processing dir
    srt_path: Path | None = None
    stem = src.stem
    for candidate in settings.processing_dir.rglob(f"{stem}*.srt"):
        srt_path = candidate
        break

    if req.subtitle_mode in ("embed", "both") and srt_path:
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        existing_vf = next((cmd[i + 1] for i, a in enumerate(cmd) if a == "-vf"), None)
        if existing_vf:
            idx = cmd.index("-vf")
            cmd[idx + 1] = existing_vf + f",subtitles='{srt_escaped}'"
        else:
            cmd += ["-vf", f"subtitles='{srt_escaped}'"]

    if req.format != "webm":
        cmd += ["-movflags", "+faststart"]

    cmd += ["-y", str(out)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise HTTPException(500, f"FFmpeg error: {result.stderr[-500:]}")

    if not out.exists() or out.stat().st_size == 0:
        raise HTTPException(500, "Export produced empty file")

    if req.subtitle_mode in ("srt", "both") and srt_path:
        import shutil as _shutil
        _shutil.copy2(srt_path, out.with_suffix(".srt"))

    return {
        "success": True,
        "output_path": str(out),
        "size_mb": round(out.stat().st_size / 1024 / 1024, 2),
    }
