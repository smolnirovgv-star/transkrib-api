"""Admin endpoints for monitoring download chain health."""
import logging
import os
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.services.health_monitor import run_full_healthcheck

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _verify_admin_token(x_admin_token: Optional[str]) -> None:
    """Verify request has correct admin token. Raises HTTPException if not."""
    expected = os.getenv("ADMIN_HEALTHCHECK_TOKEN")
    if not expected:
        logger.error("ADMIN_HEALTHCHECK_TOKEN env var not set")
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/health-check")
async def trigger_health_check(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    test_url: Optional[str] = None,
):
    """Manually trigger a full health check of all download methods.

    Stage 1 — manual only. No DB writes, no scheduling.

    Required header: X-Admin-Token: <token from env>
    Optional query param: test_url=<custom URL to test>
    """
    _verify_admin_token(x_admin_token)
    logger.info("[admin_health] manual health check triggered")
    report = await run_full_healthcheck(test_url=test_url)
    logger.info(
        "[admin_health] check completed: %d/%d ok",
        report["summary"]["ok"],
        report["summary"]["total"]
    )
    return report


@router.get("/health-status")
async def get_health_status(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    window: str = "1h",
):
    """Aggregated healthcheck stats for a given time window (1h, 24h, 7d).
    Required header: X-Admin-Token
    Query param: ?window=1h|24h|7d (default: 1h)
    """
    _verify_admin_token(x_admin_token)
    import os
    from datetime import datetime, timezone, timedelta
    from supabase import create_client
    windows = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
    if window not in windows:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="window must be 1h, 24h or 7d")
    since = (datetime.now(timezone.utc) - windows[window]).isoformat()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        sb = create_client(url, key)
        resp = sb.table("download_healthcheck").select("method,ok,latency_ms").gte("ts", since).execute()
        rows = resp.data or []
    except Exception as e:
        logger.error("[health_status] Supabase query failed: %s", e)
        raise HTTPException(status_code=503, detail="DB query failed")
    from collections import defaultdict
    stats = defaultdict(lambda: {"total": 0, "ok": 0, "latencies": []})
    for row in rows:
        m = row["method"]
        stats[m]["total"] += 1
        if row["ok"]:
            stats[m]["ok"] += 1
        if row["latency_ms"] is not None:
            stats[m]["latencies"].append(row["latency_ms"])
    result = {}
    for method, s in stats.items():
        lats = s["latencies"]
        result[method] = {
            "total": s["total"],
            "ok": s["ok"],
            "fail_rate_pct": round((1 - s["ok"] / s["total"]) * 100, 1) if s["total"] else 0,
            "avg_latency_ms": round(sum(lats) / len(lats)) if lats else None,
            "p95_latency_ms": round(sorted(lats)[int(len(lats) * 0.95)]) if lats else None,
        }
    return {"window": window, "since": since, "methods": result, "total_rows": len(rows)}
