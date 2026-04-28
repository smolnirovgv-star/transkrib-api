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
    _asyncio.create_task(_tmp_cleanup_worker())
    logger.info("[startup] tmp cleanup worker started (TTL=30min)")
    logger.info("Transkrib API (Railway) starting...")
    logger.info("Python path: %s", os.environ.get("PYTHONPATH", "not set"))
    logger.info("PORT: %s", os.environ.get("PORT", "not set"))
    yield
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
