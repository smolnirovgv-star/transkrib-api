"""
Watchdog Stage 3 — alert logic.
Sends Telegram alerts when a download method fails 3 times in a row.
Anti-spam: no repeated alerts within 1 hour per method.
Recovered: notifies when a previously failing method comes back.
State is in-memory (resets on restart — acceptable for anti-spam).
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

CONSECUTIVE_FAILS_THRESHOLD = 3
ALERT_COOLDOWN_HOURS = 1

_alert_state: dict[str, dict] = {
    method: {"alerted": False, "last_alert_ts": None}
    for method in ("yt_dlp", "rapidapi", "cobalt", "supadata", "telegram_direct")
}

METHOD_LABELS = {
    "yt_dlp": "yt-dlp",
    "rapidapi": "RapidAPI",
    "cobalt": "Cobalt",
    "supadata": "Supadata",
    "telegram_direct": "Telegram Direct",
}


async def _send_telegram(text: str) -> None:
    """Send message to admin chat via ADMIN_BOT_TOKEN. Silent on failure."""
    token = os.getenv("WATCHDOG_BOT_TOKEN") or os.getenv("ADMIN_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_CHAT_ID")
    if not token or not chat_id:
        logger.warning("[watchdog_alerts] ADMIN_BOT_TOKEN or ADMIN_CHAT_ID not set — skipping alert")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
        logger.info("[watchdog_alerts] alert sent: %s", text[:80])
    except Exception as e:
        logger.error("[watchdog_alerts] failed to send alert: %s", e)


async def _get_consecutive_fails(method: str) -> int:
    """
    Query Supabase for the last 3 records of this method.
    Returns count of consecutive fails from the most recent going back.
    Returns 0 if Supabase unavailable.
    """
    import os
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return 0
    try:
        sb = create_client(url, key)
        resp = (
            sb.table("download_healthcheck")
            .select("ok")
            .eq("method", method)
            .order("ts", desc=True)
            .limit(CONSECUTIVE_FAILS_THRESHOLD)
            .execute()
        )
        rows = resp.data or []
        if len(rows) < CONSECUTIVE_FAILS_THRESHOLD:
            return 0
        return sum(1 for r in rows if not r["ok"])
    except Exception as e:
        logger.error("[watchdog_alerts] Supabase query failed for method %s: %s", method, e)
        return 0


def _cooldown_expired(method: str) -> bool:
    """Returns True if enough time has passed since last alert for this method."""
    last_ts = _alert_state[method]["last_alert_ts"]
    if last_ts is None:
        return True
    return datetime.now(timezone.utc) - last_ts > timedelta(hours=ALERT_COOLDOWN_HOURS)


async def check_and_alert(results: list) -> None:
    """
    Called after every healthcheck run.
    results: list of HealthResult objects.
    For each failed method: check consecutive fails in DB, send alert if threshold reached.
    For each recovered method: send recovered notification.
    """
    for result in results:
        method = result.method
        label = METHOD_LABELS.get(method, method)
        state = _alert_state[method]

        if not result.ok:
            consecutive = await _get_consecutive_fails(method)
            if consecutive >= CONSECUTIVE_FAILS_THRESHOLD and _cooldown_expired(method):
                error_info = result.error or "no details"
                text = (
                    f"🔴 <b>Watchdog Alert</b>\n"
                    f"Метод <b>{label}</b> упал {consecutive} раза подряд.\n"
                    f"Ошибка: <code>{error_info[:200]}</code>\n"
                    f"Время: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                )
                await _send_telegram(text)
                state["alerted"] = True
                state["last_alert_ts"] = datetime.now(timezone.utc)
        else:
            if state["alerted"]:
                text = (
                    f"✅ <b>Watchdog Recovered</b>\n"
                    f"Метод <b>{label}</b> снова работает.\n"
                    f"Время: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                )
                await _send_telegram(text)
                state["alerted"] = False
                state["last_alert_ts"] = None
