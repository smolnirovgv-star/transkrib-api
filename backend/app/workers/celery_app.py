"""Celery application instance and configuration."""

from celery import Celery
from ..config import settings

celery_app = Celery(
    "video_processor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=1,  # Whisper is GPU-bound, one task at a time
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
