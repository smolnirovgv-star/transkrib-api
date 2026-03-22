"""System endpoints: health check, info."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models.schemas import SystemInfo
from ..services.ffmpeg_service import FFmpegService
from ..services.storage_service import StorageService

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/info", response_model=SystemInfo)
async def system_info():
    """System capabilities and stats."""
    ffmpeg_version = None
    try:
        ffmpeg = FFmpegService(settings.ffmpeg_path)
        ffmpeg_version = ffmpeg.get_version()
    except Exception:
        pass

    storage = StorageService(
        settings.upload_dir, settings.processing_dir,
        settings.result_dir, settings.log_dir,
    )
    results_count = len(list(settings.result_dir.glob("*.mp4"))) if settings.result_dir.exists() else 0

    return SystemInfo(
        ffmpeg_version=ffmpeg_version,
        whisper_model=settings.whisper_model,
        claude_model=settings.claude_model,
        storage_used_mb=storage.get_storage_used_mb(),
        results_count=results_count,
    )


@router.get("/dev/status")
async def dev_status():
    """Dev mode status — only available when APP_DEV_MODE=true."""
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")
    return {"dev_mode": True, "trial_bypassed": True}
