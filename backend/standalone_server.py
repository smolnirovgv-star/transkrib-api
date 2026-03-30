"""
Standalone FastAPI server для desktop deployment.

Без Redis, без Celery — все обработки в threading.Thread.
Точка входа для PyInstaller (backend.exe).
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# PyInstaller frozen detection
if getattr(sys, "frozen", False):
    # Когда упаковано PyInstaller — sys._MEIPASS содержит temp extraction dir
    BASE_DIR = Path(sys._MEIPASS)

    # FFmpeg binaries находятся в _MEIPASS/ffmpeg/
    ffmpeg_dir = BASE_DIR / "ffmpeg"
    if ffmpeg_dir.exists():
        # Добавляем в PATH для subprocess.run
        os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
        os.environ["APP_FFMPEG_PATH"] = str(ffmpeg_dir / "ffmpeg.exe")

    # yt-dlp.exe находится в корне _MEIPASS
    ytdlp_exe = BASE_DIR / "yt-dlp.exe"
    if ytdlp_exe.exists():
        os.environ["YTDLP_PATH"] = str(ytdlp_exe)

    # ── Isolation: redirect ALL library caches to AppData\Roaming\Transkrib\storage\
    # APP_STORAGE_DIR is injected by Electron's backend.ts before this process starts.
    # Must be set BEFORE any ML library imports so their module-level code picks it up.
    _storage_dir = Path(
        os.environ.get(
            "APP_STORAGE_DIR",
            Path.home() / "AppData" / "Roaming" / "Transkrib" / "storage",
        )
    )

    # PyTorch hub / weights cache  (default: %APPDATA%\torch)
    os.environ.setdefault("TORCH_HOME", str(_storage_dir / "torch_models"))

    # Numba JIT compilation cache  (default: %LOCALAPPDATA%\numba_cache)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(_storage_dir / "numba_cache"))

    # tiktoken BPE tokenizer cache  (default: %LOCALAPPDATA%\tiktoken_cache)
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(_storage_dir / "tiktoken_cache"))

    # HuggingFace hub cache (not used now, but guard against future deps)
    os.environ.setdefault("HF_HOME", str(_storage_dir / "hf_models"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(_storage_dir / "hf_models"))

    # Redirect Python's tempfile to app temp dir (used by ffmpeg_service and pipeline)
    import tempfile
    _tmp_dir = _storage_dir / "temp"
    _tmp_dir.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(_tmp_dir)

    # Normalize APP_STORAGE_DIR so pydantic Settings reads the exact canonical path
    os.environ["APP_STORAGE_DIR"] = str(_storage_dir)

    # Whisper model cache — explicit env var used by TranscriptionService as primary source
    _whisper_cache = _storage_dir / "whisper_models"
    _whisper_cache.mkdir(parents=True, exist_ok=True)
    os.environ["APP_WHISPER_CACHE_DIR"] = str(_whisper_cache)

else:
    BASE_DIR = Path(__file__).parent

# Configure logging BEFORE importing app modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("video_processor.standalone")

# File logging (frozen/installed mode only)
if getattr(sys, "frozen", False):
    _log_dir = _storage_dir / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_file = _log_dir / "backend.log"
    _fh = logging.FileHandler(str(_log_file), encoding="utf-8", mode="a")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger().addHandler(_fh)
    logger.info(f"Logging to file: {_log_file}")

# Now import app modules
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import results, system, export as export_router, preview as preview_router, transcript as transcript_router
from app.routers.payments import router as payments_router
from app.workers.memory_progress import InMemoryProgressReporter
from app.workers.standalone_tasks import (
    init_progress,
    init_trial_manager,
    run_video_task,
    run_url_task,
    get_storage_service,
    preload_whisper_model,
)
from app.websocket.memory_manager import InMemoryConnectionManager
from app.routers.standalone_tasks_router import (
    router as tasks_router,
    set_dependencies as set_tasks_deps,
)
from app.routers.standalone_ws_router import create_ws_router
from app.license import LicenseManager
from app.trial import TrialManager

# Shared instances
progress_reporter = InMemoryProgressReporter()
ws_manager = InMemoryConnectionManager(progress_reporter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context — startup and shutdown logic.
    """
    import time as _time
    _t0 = _time.perf_counter()
    def _ts(label): logger.info(f"[TIMING] {label}: +{_time.perf_counter()-_t0:.2f}s")
    logger.info("=" * 60)
    logger.info("Transkrib Standalone Server starting...")
    logger.info("=" * 60)

    # Get event loop and inject into progress reporter (для WebSocket cross-thread push)
    loop = asyncio.get_running_loop()
    progress_reporter.set_event_loop(loop)

    # Initialize standalone task runner
    init_progress(progress_reporter)
    _ts("progress_reporter ready")

    # Initialize storage service and inject into tasks router
    storage = get_storage_service()

    # Define pipeline runner wrapper (для compatibility с router signature)
    def video_pipeline_runner(task_id: str, file_path: str, original_name: str):
        run_video_task(task_id, file_path, original_name)

    def url_pipeline_runner(task_id: str, url: str):
        run_url_task(task_id, url)

    # Для tasks router нужна универсальная функция, которая определяет тип задачи
    def universal_runner(task_id: str, path_or_url: str, original_name: str = None, max_duration_seconds: int = None, whisper_model: str = None):
        if original_name:
            run_video_task(task_id, path_or_url, original_name, max_duration_seconds=max_duration_seconds, whisper_model=whisper_model)
        else:
            run_url_task(task_id, path_or_url, max_duration_seconds=max_duration_seconds, whisper_model=whisper_model)

    # Instantiate TrialManager early — its __init__ starts background hardware+time prefetch
    # while FFmpeg validation and license check run, overlapping the slow wmic calls
    _ts("trial manager pre-init")
    trial_manager = TrialManager(settings.storage_dir)

    # Create storage directories (all isolated within APP_STORAGE_DIR)
    _extra_cache_dirs = [
        settings.storage_dir / "numba_cache",
        settings.storage_dir / "torch_models",
        settings.storage_dir / "hf_models",
    ]
    for directory in [
        settings.upload_dir,
        settings.processing_dir,
        settings.result_dir,
        settings.log_dir,
        settings.temp_dir,
        settings.whisper_cache_dir,
        *_extra_cache_dirs,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"ENV APP_STORAGE_DIR={os.environ.get('APP_STORAGE_DIR')}")
    logger.info(f"ENV APP_WHISPER_CACHE_DIR={os.environ.get('APP_WHISPER_CACHE_DIR')}")
    logger.info(f"settings.storage_dir={settings.storage_dir}")
    logger.info(f"Whisper cache dir: {settings.whisper_cache_dir}")
    # faster-whisper stores models in subfolders (HuggingFace cache format), not .pt files
    _cached = [p.name for p in settings.whisper_cache_dir.iterdir() if p.is_dir()] if settings.whisper_cache_dir.exists() else []
    logger.info(f"Cached faster-whisper models: {_cached}")

    # Validate FFmpeg
    from app.services.ffmpeg_service import FFmpegService
    ffmpeg = FFmpegService(settings.ffmpeg_path)
    _ts("ffmpeg validated")
    logger.info(f"FFmpeg found: {ffmpeg.ffmpeg_path}")
    logger.info(f"FFprobe found: {ffmpeg.ffprobe_path}")

    # Initialize license manager
    license_manager = LicenseManager(settings.storage_dir / ".license")
    is_licensed, license_msg = license_manager.is_licensed()
    _ts("license checked")
    logger.info(f"License status: {license_msg}")

    # Store in app state for access from license endpoints
    app.state.license_manager = license_manager

    # Initialize trial manager (already instantiated above; background prefetch is running)
    _ts("trial init start")
    trial_status = trial_manager.init_trial()   # returns status, no need for 2nd get_status() call
    app.state.trial_manager = trial_manager
    _ts("trial init done")
    logger.info(f"Trial status: {trial_status['state']} ({trial_status.get('remaining_days', 0)} days remaining)")

    # Inject trial manager into background task runner (for post-processing recording)
    init_trial_manager(trial_manager)

    # Wire up tasks router with storage, pipeline runner, and protection managers
    set_tasks_deps(storage, progress_reporter, universal_runner,
                   trial_manager=trial_manager, license_manager=license_manager)

    _ts("startup complete")
    logger.info("Startup complete — ready to accept requests")

    # Pre-warm Whisper model in background — so first video doesn't wait for model load
    import threading as _threading
    def _warm_whisper():
        try:
            logger.info("[Whisper] Background pre-warm started...")
            preload_whisper_model()
            logger.info("[Whisper] Model warm and ready in memory")
        except Exception as _e:
            logger.warning(f"[Whisper] Pre-warm failed (will load on demand): {_e}")
    _threading.Thread(target=_warm_whisper, daemon=True, name="whisper-prewarm").start()

    yield

    logger.info("Shutting down standalone server...")


# Create FastAPI app
app = FastAPI(
    title="Transkrib Standalone API",
    version="1.0.0",
    description="Video transcription and highlights extraction (standalone desktop mode)",
    lifespan=lifespan,
)

# Global exception handler — return real error detail instead of generic "Internal Server Error"
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    from fastapi import HTTPException as _HTTPException
    if isinstance(exc, _HTTPException):
        raise exc
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False with allow_origins=["*"]; True causes ACAO:null for file:// pages
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logger — log ALL incoming requests so we can see what reaches the backend
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _Req

class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: _Req, call_next):
        logger.info(f">> {request.method} {request.url.path} origin={request.headers.get('origin','—')}")
        try:
            response = await call_next(request)
            logger.info(f"<< {request.method} {request.url.path} -> {response.status_code}")
            return response
        except Exception as exc:
            logger.error(f"!! {request.method} {request.url.path} -> EXCEPTION: {exc}")
            raise

app.add_middleware(_RequestLogMiddleware)

# Register routers
app.include_router(tasks_router)
app.include_router(results.router)
app.include_router(system.router)
app.include_router(create_ws_router(ws_manager))
app.include_router(export_router.router)
app.include_router(preview_router.router)
app.include_router(transcript_router.router)
app.include_router(payments_router)

# License management endpoints
from fastapi import HTTPException
from pydantic import BaseModel

class LicenseActivationRequest(BaseModel):
    key: str

@app.get("/api/system/license")
async def get_license_status():
    """Check if application is licensed."""
    license_manager: LicenseManager = app.state.license_manager
    return license_manager.get_license_info()

@app.post("/api/system/activate")
async def activate_license(request: LicenseActivationRequest):
    """Activate license with a key."""
    license_manager: LicenseManager = app.state.license_manager
    success, message = license_manager.activate(request.key)

    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@app.get("/api/system/trial")
async def get_trial_status():
    """Get trial period status."""
    trial_manager: TrialManager = app.state.trial_manager
    return trial_manager.get_status()


@app.post("/api/system/trial/record")
async def record_trial_video():
    """Record a processed video against trial limits."""
    trial_manager: TrialManager = app.state.trial_manager
    allowed, reason = trial_manager.can_process()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    trial_manager.record_video()
    return {"recorded": True}

@app.post("/api/system/prepare-whisper")
async def prepare_whisper():
    """Pre-download Whisper model (для первого запуска)."""
    def _download():
        from app.services.transcription_service import TranscriptionService
        logger.info("Pre-downloading Whisper model...")
        svc = TranscriptionService(settings.whisper_model, settings.whisper_cache_dir)
        svc.ensure_model()
        logger.info("Whisper model ready")

    import threading
    thread = threading.Thread(target=_download, daemon=True)
    thread.start()

    return {
        "status": "downloading",
        "model": settings.whisper_model,
        "message": "Whisper model download started in background",
    }

@app.get("/api/system/whisper-status")
async def whisper_status():
    """Check if Whisper model is downloaded."""
    model_name = settings.whisper_model
    model_path = settings.whisper_cache_dir / f"{model_name}.pt"

    if model_path.exists():
        size_mb = round(model_path.stat().st_size / (1024 * 1024), 1)
        return {
            "downloaded": True,
            "model": model_name,
            "path": str(model_path),
            "size_mb": size_mb,
        }
    else:
        return {
            "downloaded": False,
            "model": model_name,
            "path": str(model_path),
            "size_mb": 0,
        }


if __name__ == "__main__":
    # Port configuration
    port = int(os.environ.get("PORT", os.environ.get("TRANSKRIB_PORT", "8000")))

    logger.info(f"Starting uvicorn server on http://127.0.0.1:{port}")

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=port,
        log_level="info",
        access_log=True,
    )
