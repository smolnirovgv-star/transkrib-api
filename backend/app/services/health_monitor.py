"""
Health monitor for download chain.
Runs each of the 5 download methods on a test URL and reports timing/result.
Stage 1 — manual trigger only. No DB writes, no scheduling, no alerts.
"""
import asyncio
import logging
import os
import re
import time
from datetime import timezone, datetime
from dataclasses import dataclass, asdict
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _get_cookie_file_for_health():
    """Декодирует YOUTUBE_COOKIES_B64 в temp-файл. Изолированная копия логики из bot_tasks."""
    import base64, tempfile
    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if not b64:
        secret_path = "/etc/secrets/YOUTUBE_COOKIES_B64"
        if os.path.exists(secret_path):
            try:
                with open(secret_path) as f:
                    b64 = f.read().strip()
            except Exception:
                pass
    if not b64:
        return None
    try:
        cookie_data = base64.b64decode(b64).decode("utf-8")
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write(cookie_data)
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.warning("[health] cookies decode failed: %s", e)
        return None


def _get_proxy_url_for_health():
    """Возвращает proxy URL из ENV — никаких захардкоженных дефолтов."""
    return (
        os.environ.get("YOUTUBE_PROXY", "").strip()
        or os.environ.get("WEBSHARE_PROXY", "").strip()
    )


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
    """Check yt-dlp: extract info with cookies+proxy+extractor_args (same config as production)."""
    start = time.perf_counter()
    cookie_path = _get_cookie_file_for_health()
    proxy_url = _get_proxy_url_for_health()
    logger.info("[health] yt_dlp check: cookies=%s proxy=%s",
                "yes" if cookie_path else "no",
                "yes" if proxy_url else "no")
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 15,
            'extractor_args': {
                'youtube': {'player_client': ['tv', 'android_vr', 'web_safari']}
            },
        }
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
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
            bytes_downloaded=0  # metadata-only probe, no actual download
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(
            method="yt_dlp",
            ok=False,
            latency_ms=latency_ms,
            error=str(e)[:200]
        )
    finally:
        if cookie_path and os.path.exists(cookie_path):
            try:
                os.unlink(cookie_path)
            except Exception:
                pass


async def _check_rapidapi(url: str) -> HealthResult:
    """Check RapidAPI YouTube Media Downloader reachability.
    Uses the same API endpoint as production downloads (bot_tasks.py)."""
    start = time.perf_counter()
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if not rapidapi_key:
        return HealthResult(method="rapidapi", ok=False, latency_ms=0,
                            error="RAPIDAPI_KEY env var missing")
    # Extract video ID from URL (same logic as bot_tasks._extract_youtube_id)
    m = re.search(
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        url
    )
    if not m:
        return HealthResult(method="rapidapi", ok=False, latency_ms=0,
                            error="failed to extract video_id from test URL")
    video_id = m.group(1)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://youtube-media-downloader.p.rapidapi.com/v2/video/details",
                params={
                    "videoId": video_id,
                    "urlAccess": "normal",
                    "videos": "auto",
                    "audios": "auto",
                },
                headers={
                    "x-rapidapi-host": "youtube-media-downloader.p.rapidapi.com",
                    "x-rapidapi-key": rapidapi_key,
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
        return HealthResult(method="rapidapi", ok=False, latency_ms=latency_ms,
                            error=str(e)[:200])


async def _check_cobalt(url: str) -> HealthResult:
    """Check Cobalt: verify API reachability AND actual file delivery (>10 KB)."""
    start = time.perf_counter()
    cobalt_url = os.getenv("COBALT_API_URL", "https://cobalt-production-f557.up.railway.app")
    direct_url = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                cobalt_url + "/",
                json={
                    "url": url,
                    "videoQuality": "480",
                    "downloadMode": "auto",
                    "filenameStyle": "basic",
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code != 200:
            return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                                error=f"HTTP {resp.status_code}")
        data = resp.json()
        status = data.get("status")
        if status not in ("tunnel", "redirect", "stream"):
            return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                                error=f"unexpected status: {status}")
        direct_url = data.get("url")
        if not direct_url:
            return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                                error="no url in cobalt response")
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                            error=str(e)[:200])

    # Download first 50 KB to verify actual content delivery
    try:
        total = 0
        async with httpx.AsyncClient(timeout=20.0) as dl_client:
            async with dl_client.stream("GET", direct_url,
                                        headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status_code != 200:
                    return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                                        error=f"download HTTP {r.status_code}")
                async for chunk in r.aiter_bytes(8192):
                    total += len(chunk)
                    if total >= 50000:
                        break
        latency_ms = int((time.perf_counter() - start) * 1000)
        if total < 10000:
            return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                                error=f"cobalt returned empty stream: {total} bytes")
        return HealthResult(method="cobalt", ok=True, latency_ms=latency_ms,
                            bytes_downloaded=total)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(method="cobalt", ok=False, latency_ms=latency_ms,
                            error=str(e)[:200])


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
    """Check Telegram Bot API reachability via getMe endpoint.

    This is the same API surface used by bot.py for downloading user-uploaded
    videos via Telegram CDN URL. Uses ADMIN_BOT_TOKEN if available; falls back
    to TELEGRAM_BOT_TOKEN. HTTP 200 = bot reachable. HTTP 401 = token wrong
    but server alive (still ok for is API reachable check).
    """
    start = time.perf_counter()
    token = os.getenv("ADMIN_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return HealthResult(method="telegram_direct", ok=False, latency_ms=0,
                            error="No bot token in env (ADMIN_BOT_TOKEN or TELEGRAM_BOT_TOKEN)")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        latency_ms = int((time.perf_counter() - start) * 1000)
        ok = resp.status_code in (200, 401)
        return HealthResult(
            method="telegram_direct",
            ok=ok,
            latency_ms=latency_ms,
            bytes_downloaded=len(resp.content),
            error=None if ok else f"HTTP {resp.status_code}"
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return HealthResult(method="telegram_direct", ok=False, latency_ms=latency_ms,
                            error=str(e)[:200])


async def _save_to_supabase(results: list, test_source: str = "scheduler") -> None:
    """Write 5 health check rows to download_healthcheck table. Silent on failure."""
    import os
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.warning("[health_monitor] SUPABASE_URL or SUPABASE_KEY not set — skipping DB write")
        return
    try:
        sb = create_client(url, key)
        rows = [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "method": r.method,
                "ok": r.ok,
                "latency_ms": r.latency_ms,
                "bytes_downloaded": r.bytes_downloaded,
                "error_message": r.error,
                "test_source": test_source,
            }
            for r in results
        ]
        sb.table("download_healthcheck").insert(rows).execute()
        logger.info("[health_monitor] saved %d rows to download_healthcheck", len(rows))
    except Exception as e:
        logger.error("[health_monitor] failed to save to Supabase: %s", e)


async def run_full_healthcheck(test_url=None, test_source: str = "manual") -> dict:
    """Run all 5 method checks in parallel and return aggregated report."""
    url = test_url or DEFAULT_TEST_URL
    logger.info("[health_monitor] starting full check on %s", url)
    results = await asyncio.gather(
        _check_yt_dlp(url),
        _check_rapidapi(url),
        _check_cobalt(url),
        _check_supadata(url),
        _check_telegram_direct(),
        return_exceptions=False
    )
    await _save_to_supabase(results, test_source=test_source)
    from app.services.watchdog_alerts import check_and_alert
    await check_and_alert(results)
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
