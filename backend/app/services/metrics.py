import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)
_supabase_client = None


def _get_client():
    """Lazily creates Supabase client. Returns None if env vars missing."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.warning("[METRICS] SUPABASE_URL or SUPABASE_KEY not set -- metrics disabled")
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        logger.warning("[METRICS] Failed to create Supabase client: %s", e)
        return None


def record_task_metric(
    task_id: str,
    final_status: str,
    cut_status: Optional[str] = None,
    download_method: Optional[str] = None,
    formatter_status: Optional[str] = None,
    processing_time_sec: Optional[int] = None,
) -> None:
    """Write one row to task_metrics. Never raises."""
    try:
        client = _get_client()
        if client is None:
            return
        payload = {
            "task_id": task_id,
            "final_status": final_status,
            "cut_status": cut_status or "not_requested",
            "download_method": download_method or "not_youtube",
            "formatter_status": formatter_status or "not_requested",
        }
        if processing_time_sec is not None:
            payload["processing_time_sec"] = int(processing_time_sec)
        # upsert handles retry duplicates gracefully
        client.table("task_metrics").upsert(payload).execute()
        logger.info(
            "[METRICS] Recorded task %s: final=%s cut=%s dl=%s fmt=%s time=%ss",
            task_id, final_status, cut_status, download_method, formatter_status, processing_time_sec,
        )
    except Exception as e:
        # Never propagate. Metrics are optional.
        logger.warning("[METRICS] Failed to record metric for task %s: %s", task_id, e)
