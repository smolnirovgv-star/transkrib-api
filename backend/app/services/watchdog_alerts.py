"""
Watchdog Stage 3 — alert logic.
Sends Telegram alerts when a download method fails 3 times in a row.
Anti-spam: no repeated alerts within 24 hours per method.
Recovered: notifies when a previously failing method comes back.
State is persisted in Supabase watchdog_alert_state (survives Railway restarts).
Daily digest via send_daily_digest() provides a 24-hour summary of all methods.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

CONSECUTIVE_FAILS_THRESHOLD = 3
ALERT_COOLDOWN_HOURS = 24

KNOWN_METHODS = ("yt_dlp", "rapidapi", "cobalt", "supadata", "telegram_direct")

METHOD_LABELS = {
    "yt_dlp": "yt-dlp",
    "rapidapi": "RapidAPI",
    "cobalt": "Cobalt",
    "supadata": "Supadata",
    "telegram_direct": "Telegram Direct",
}

# In-memory fallback — used when Supabase is unavailable
_alert_state_fallback: dict[str, dict] = {
    method: {"alerted": False, "last_alert_ts": None}
    for method in KNOWN_METHODS
}


def _get_supabase():
    """Return Supabase client or None if env not set."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


async def _load_alert_state(method: str) -> dict:
    """Read alert state from Supabase for this method. Falls back to in-memory."""
    try:
        sb = _get_supabase()
        if not sb:
            return dict(_alert_state_fallback[method])
        resp = (
            sb.table("watchdog_alert_state")
            .select("alerted,last_alert_ts")
            .eq("method", method)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return {"alerted": False, "last_alert_ts": None}
        row = rows[0]
        last_ts = None
        if row.get("last_alert_ts"):
            last_ts = datetime.fromisoformat(row["last_alert_ts"].replace("Z", "+00:00"))
        return {"alerted": row["alerted"], "last_alert_ts": last_ts}
    except Exception as e:
        logger.warning("[watchdog_alerts] load_alert_state failed for %s: %s", method, e)
        return dict(_alert_state_fallback.get(method, {"alerted": False, "last_alert_ts": None}))


async def _save_alert_state(method: str, alerted: bool, last_alert_ts: Optional[datetime]) -> None:
    """Persist alert state to Supabase. Always updates in-memory fallback too."""
    _alert_state_fallback[method] = {"alerted": alerted, "last_alert_ts": last_alert_ts}
    ts_str = last_alert_ts.isoformat() if last_alert_ts else None
    try:
        sb = _get_supabase()
        if not sb:
            return
        sb.table("watchdog_alert_state").upsert(
            {"method": method, "alerted": alerted, "last_alert_ts": ts_str},
            on_conflict="method",
        ).execute()
    except Exception as e:
        logger.warning("[watchdog_alerts] save_alert_state failed for %s: %s", method, e)


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
    try:
        sb = _get_supabase()
        if not sb:
            return 0
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


def _cooldown_expired(last_alert_ts: Optional[datetime]) -> bool:
    """Returns True if enough time has passed since last alert."""
    if last_alert_ts is None:
        return True
    return datetime.now(timezone.utc) - last_alert_ts > timedelta(hours=ALERT_COOLDOWN_HOURS)


async def check_and_alert(results: list) -> None:
    """
    Called after every healthcheck run.
    results: list of HealthResult objects.
    For each failed method: check consecutive fails in DB, send alert if threshold reached.
    For each recovered method: send recovered notification.
    State is read from / written to Supabase (persists across restarts).
    """
    for result in results:
        method = result.method
        label = METHOD_LABELS.get(method, method)
        state = await _load_alert_state(method)

        if not result.ok:
            consecutive = await _get_consecutive_fails(method)
            if consecutive >= CONSECUTIVE_FAILS_THRESHOLD and _cooldown_expired(state["last_alert_ts"]):
                error_info = result.error or "no details"
                text = (
                    f"\U0001f534 <b>Watchdog Alert</b>\n"
                    f"Метод <b>{label}</b> упал {consecutive} раза подряд.\n"
                    f"Ошибка: <code>{error_info[:200]}</code>\n"
                    f"Время: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                )
                await _send_telegram(text)
                await _save_alert_state(method, alerted=True, last_alert_ts=datetime.now(timezone.utc))
        else:
            if state["alerted"]:
                text = (
                    f"\u2705 <b>Watchdog Recovered</b>\n"
                    f"Метод <b>{label}</b> снова работает.\n"
                    f"Время: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                )
                await _send_telegram(text)
                await _save_alert_state(method, alerted=False, last_alert_ts=None)


async def send_daily_digest() -> None:
    """
    Send a daily digest of all 5 methods to @TranskribAdmin_Bot.
    Shows ok/total counts and last error for each method over the past 24 hours.
    Registered as APScheduler job in main_railway.py (every 24 hours).
    """
    try:
        sb = _get_supabase()
        if not sb:
            logger.warning("[watchdog_alerts] send_daily_digest: Supabase not configured")
            return
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        resp = (
            sb.table("download_healthcheck")
            .select("method,ok,error_message,ts")
            .gte("ts", since)
            .order("ts", desc=True)
            .execute()
        )
        rows = resp.data or []
        from collections import defaultdict
        stats: dict = defaultdict(lambda: {"total": 0, "ok": 0, "last_error": None})
        for r in rows:
            m = r["method"]
            stats[m]["total"] += 1
            if r["ok"]:
                stats[m]["ok"] += 1
            elif stats[m]["last_error"] is None and r.get("error_message"):
                stats[m]["last_error"] = r["error_message"]

        lines = [
            "\U0001f4ca <b>Watchdog Daily Digest</b>",
            "За последние 24\u00a0ч:",
            "",
        ]
        for method in KNOWN_METHODS:
            label = METHOD_LABELS.get(method, method)
            s = stats.get(method, {"total": 0, "ok": 0, "last_error": None})
            total = s["total"]
            ok = s["ok"]
            if total == 0:
                line = f"\u26aa <b>{label}</b>: нет данных"
            elif ok == total:
                line = f"\u2705 <b>{label}</b>: {ok}/{total}"
            elif ok == 0:
                err = (s["last_error"] or "")[:80]
                line = f"\U0001f534 <b>{label}</b>: 0/{total} — <code>{err}</code>"
            else:
                err = (s["last_error"] or "")[:60]
                line = f"\U0001f7e1 <b>{label}</b>: {ok}/{total} — <code>{err}</code>"
            lines.append(line)

        lines.append("")
        lines.append(f"\U0001f551 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}")
        await _send_telegram("\n".join(lines))
        logger.info("[watchdog_alerts] daily digest sent")
    except Exception as e:
        logger.error("[watchdog_alerts] send_daily_digest failed: %s", e)


LIMITS = {
    "rapidapi": {"monthly": 500, "name": "RapidAPI"},
    "supadata": {"monthly": 150, "name": "Supadata (paid ~$10/мес)"},
    "yt_dlp": {"monthly": 999999, "name": "yt-dlp (бесплатно)"},
    "cobalt": {"monthly": 999999, "name": "Cobalt (self-hosted)"},
    "telegram_direct": {"monthly": 999999, "name": "Telegram Direct"},
}


async def send_usage_report() -> None:
    """Send usage report every 3 days via @TranskribAdmin_Bot."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return
    try:
        sb = create_client(url, key)
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        resp = sb.table("download_healthcheck").select("method,ok").gte("ts", since).execute()
        rows = resp.data or []
        from collections import defaultdict
        counts: dict = defaultdict(lambda: {"total": 0, "ok": 0})
        for r in rows:
            counts[r["method"]]["total"] += 1
            if r["ok"]:
                counts[r["method"]]["ok"] += 1

        lines = ["\U0001f4ca <b>Отчёт расходов Watchdog (30 дней)</b>\n"]
        for method, info in LIMITS.items():
            c = counts.get(method, {"total": 0, "ok": 0})
            total = c["total"]
            limit = info["monthly"]
            if limit < 999999:
                pct = round(total / limit * 100, 1)
                status = "\U0001f534" if pct > 80 else "\U0001f7e1" if pct > 50 else "\U0001f7e2"
                lines.append(f"{status} <b>{info['name']}</b>: {total}/{limit} ({pct}%)")
            else:
                lines.append(f"\U0001f7e2 <b>{info['name']}</b>: {total} запросов (без лимита)")

        lines.append(f"\n\U0001f550 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}")
        await _send_telegram("\n".join(lines))
        logger.info("[watchdog_alerts] usage report sent")
    except Exception as e:
        logger.error("[watchdog_alerts] usage report failed: %s", e)
