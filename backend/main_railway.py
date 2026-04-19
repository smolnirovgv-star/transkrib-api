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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"status": "ok", "service": "transkrib-api"}
