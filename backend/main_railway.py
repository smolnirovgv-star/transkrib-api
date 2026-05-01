"""Railway entry point — only bot_tasks router, no celery/faster-whisper."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("transkrib")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio as _asyncio
    from app.routers.bot_tasks import _tmp_cleanup_worker
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.services.watchdog_alerts import send_usage_report as send_usage_report_job

    _asyncio.create_task(_tmp_cleanup_worker())
    logger.info("[startup] tmp cleanup worker started (TTL=30min)")

    # Бесплатные методы — каждые 15 минут
    async def _check_free_methods():
        from app.services.health_monitor import _check_yt_dlp, _check_cobalt, _check_telegram_direct, _save_to_supabase
        from app.services.watchdog_alerts import check_and_alert
        import asyncio
        results = await asyncio.gather(
            _check_yt_dlp(os.environ.get("HEALTH_TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
            _check_cobalt(os.environ.get("HEALTH_TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
            _check_telegram_direct(),
            return_exceptions=False
        )
        await _save_to_supabase(list(results), test_source="scheduler_free")
        await check_and_alert(list(results))

    # Платные/лимитные методы — каждые 2 часа
    async def _check_paid_methods():
        from app.services.health_monitor import _check_rapidapi, _check_supadata, _save_to_supabase
        from app.services.watchdog_alerts import check_and_alert
        import asyncio
        results = await asyncio.gather(
            _check_rapidapi(os.environ.get("HEALTH_TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
            _check_supadata(os.environ.get("HEALTH_TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
            return_exceptions=False
        )
        await _save_to_supabase(list(results), test_source="scheduler_paid")
        await check_and_alert(list(results))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _check_free_methods,
        trigger="interval",
        minutes=15,
        id="watchdog_free",
        replace_existing=True,
    )
    scheduler.add_job(
        _check_paid_methods,
        trigger="interval",
        hours=2,
        id="watchdog_paid",
        replace_existing=True,
    )
    scheduler.add_job(
        send_usage_report_job,
        trigger="interval",
        days=3,
        id="usage_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[startup] watchdog scheduler started (free=15min, paid=2h, report=3d)")

    logger.info("Transkrib API (Railway) starting...")
    logger.info("Python path: %s", os.environ.get("PYTHONPATH", "not set"))
    logger.info("PORT: %s", os.environ.get("PORT", "not set"))

    yield

    scheduler.shutdown(wait=False)
    logger.info("[shutdown] watchdog scheduler stopped")
    logger.info("Transkrib API shutting down")


app = FastAPI(title="Transkrib API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from app.routers.bot_tasks import router as bot_router
    app.include_router(bot_router)
    logger.info("bot_tasks router loaded OK")
except Exception as e:
    logger.error("FAILED to load bot_tasks router: %s", e, exc_info=True)
    raise

try:
    from app.routers.bot_payments import router as bot_payments_router
    app.include_router(bot_payments_router)
    logger.info("bot_payments router loaded OK")
except Exception as e:
    logger.error("FAILED to load bot_payments router: %s", e, exc_info=True)
    raise

try:
    from app.routers import admin_health
    app.include_router(admin_health.router)
    logger.info("admin_health router loaded OK")
except Exception as e:
    logger.error("FAILED to load admin_health router: %s", e, exc_info=True)
    raise


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"status": "ok", "service": "transkrib-api"}
