"""FastAPI application factory with lifespan management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import tasks, results, system, ws

logger = logging.getLogger("video_processor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Starting Video Processor API")

    # Create storage directories
    for d in [settings.upload_dir, settings.processing_dir,
              settings.result_dir, settings.log_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Validate FFmpeg
    from .services.ffmpeg_service import FFmpegService
    try:
        ffmpeg = FFmpegService(settings.ffmpeg_path)
        logger.info(f"FFmpeg: {ffmpeg.ffmpeg_path}")
    except RuntimeError as e:
        logger.error(f"FFmpeg not found: {e}")

    logger.info("API ready")
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Transkrib Video Processor",
        description="API для обработки видео: транскрибация, анализ, сборка highlights",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tasks.router)
    app.include_router(results.router)
    app.include_router(system.router)
    app.include_router(ws.router)

    return app


app = create_app()
