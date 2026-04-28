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
