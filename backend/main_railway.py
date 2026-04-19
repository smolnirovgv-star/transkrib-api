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

from app.routers.bot_tasks import router as bot_router
app.include_router(bot_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
