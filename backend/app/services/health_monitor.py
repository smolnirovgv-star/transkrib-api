"""
Health monitor for download chain.
Runs each of the 5 download methods on a test URL and reports timing/result.
Stage 1 — manual trigger only. No DB writes, no scheduling, no alerts.
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HealthResult:
    """Result of a single download method check."""
    method: str
    ok: bool
    latency_ms: int
    bytes_downloaded: int = 0
    error: Optional[str] = None


# Test URL — public YouTube video that won't disappear
DEFAULT_TEST_URL = os.getenv(
    "HEALTH_TEST_YOUTUBE_URL",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley, 3:32
)

# How many bytes to download to count as "ok" (no need to download full file)
HEALTH_CHECK_BYTE_THRESHOLD = 50_000  # 50 KB is enough to confirm method works


async def _check_yt_dlp(url: str) -> HealthResult:
    """Check yt-dlp: try to extract info (no full download)."""
    start = time.perf_counter()
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 15,
        }
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        approx_bytes = info.get('filesize_approx', 0) if info else 0
        return HealthResult(
            method="yt_dlp",
            ok=bool(info),
            latency_ms=latency_ms,
            bytes_downloaded=approx_bytes
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="yt_dlp",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )


async def _check_rapidapi(url: str) -> HealthResult:
    """Check RapidAPI: ping the endpoint with HEAD request."""
    start = time.perf_counter()
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if not rapidapi_key:
        return HealthResult(
            method="rapidapi",
            ok=False,
            latency_ms=0,
            error="RAPIDAPI_KEY env var missing"
        )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://youtube-to-mp4.p.rapidapi.com/url",
                params={"url": url},
                headers={
                    "X-RapidAPI-Key": rapidapi_key,
                    "X-RapidAPI-Host": "youtube-to-mp4.p.rapidapi.com",
                }
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="rapidapi",
            ok=resp.status_code == 200,
            latency_ms=latency_ms,
            bytes_downloaded=len(resp.content),
            error=None if resp.status_code == 200 else f"HTTP {resp.status_code}"
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="rapidapi",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )


async def _check_cobalt(url: str) -> HealthResult:
    """Check Cobalt: ping the local instance."""
    start = time.perf_counter()
    cobalt_url = os.getenv("COBALT_API_URL", "https://cobalt-production-f557.up.railway.app")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                cobalt_url + "/",
                json={"url": url},
                headers={"Accept": "application/json"}
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="cobalt",
            ok=resp.status_code == 200,
            latency_ms=latency_ms,
            bytes_downloaded=len(resp.content),
            error=None if resp.status_code == 200 else f"HTTP {resp.status_code}"
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="cobalt",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )


async def _check_supadata(url: str) -> HealthResult:
    """Check Supadata: ping with API key."""
    start = time.perf_counter()
    supadata_key = os.getenv("SUPADATA_API_KEY")
    if not supadata_key:
        return HealthResult(
            method="supadata",
            ok=False,
            latency_ms=0,
            error="SUPADATA_API_KEY env var missing"
        )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.supadata.ai/v1/youtube/transcript",
                params={"url": url, "lang": "en"},
                headers={"x-api-key": supadata_key}
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="supadata",
            ok=resp.status_code == 200,
            latency_ms=latency_ms,
            bytes_downloaded=len(resp.content),
            error=None if resp.status_code == 200 else f"HTTP {resp.status_code}"
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="supadata",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )


async def _check_telegram_direct() -> HealthResult:
    """Check Telegram CDN reachability with HEAD request to a known public endpoint."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.telegram.org/")
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="telegram_direct",
            ok=resp.status_code in (200, 404),  # 404 is OK — server reachable
            latency_ms=latency_ms,
            bytes_downloaded=len(resp.content),
            error=None if resp.status_code in (200, 404) else f"HTTP {resp.status_code}"
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="telegram_direct",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )


async def run_full_healthcheck(test_url: Optional[str] = None) -> dict:
    """Run all 5 method checks in parallel and return aggregated report."""
    url = test_url or DEFAULT_TEST_URL
    logger.info("[health_monitor] starting full check on %s", url)

    # Run all 5 checks in parallel — saves time vs sequential
    results = await asyncio.gather(
        _check_yt_dlp(url),
        _check_rapidapi(url),
        _check_cobalt(url),
        _check_supadata(url),
        _check_telegram_direct(),
        return_exceptions=False
    )

    return {
        "ts": int(time.time()),
        "test_url": url,
        "results": [asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r.ok),
            "failed": sum(1 for r in results if not r.ok),
        }
    }
