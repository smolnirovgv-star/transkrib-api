"""
Trial period manager for Transkrib Desktop — v2.

Multi-layer protection:
  - Hardware fingerprint: CPU ID + MAC + disk serial + motherboard serial
  - Tri-storage: file (primary) + HKCU registry + HKLM registry (admin-protected)
  - Clock rollback detection via cached last-seen internet time
  - Bypass detection: >2 hardware components changed → permanent block
  - Security event log: AppData\\Roaming\\Transkrib\\security.log

All data is HMAC-signed and machine-bound (stdlib only).
Thread-safe via instance lock.
"""

import sys
import hmac
import json
import socket
import hashlib
import base64
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .fingerprint import (
    collect_components,
    build_fingerprint,
    count_component_changes,
    BYPASS_THRESHOLD,
)

logger = logging.getLogger("video_processor.trial")

_APP_SECRET = b"transkrib-trial-v1-2024-7f3a9e2c8b1d"

TRIAL_DAYS = 7
DAILY_LIMIT = 3
WARNING_DAYS = 2
MAX_VIDEO_SECONDS = 1800

_REG_HKCU_KEY   = r"SOFTWARE\Transkrib"
_REG_HKCU_VALUE = "TrialData"
_REG_HKLM_KEY   = r"SOFTWARE\Transkrib"
_REG_HKLM_VALUE = "TrialInit"

_ROLLBACK_TOLERANCE_SECONDS = 300


class TrialManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trial_file = data_dir / "trial.dat"
        self._sec_log = data_dir.parent / "security.log"
        self._lock = threading.Lock()
        self._hw_id = self._get_legacy_hw_id()
        self._mac_key = self._derive_mac_key()
        self._components_cache: dict | None = None   # cached once per process
        self._internet_time_cache: object | None = None  # last fetched internet time
        # Kick off internet time fetch in background immediately so it is ready
        # by the time init_trial() / get_status() calls _now_utc()
        threading.Thread(target=self._prefetch_internet_time, daemon=True).start()

    def _prefetch_internet_time(self) -> None:
        """Background pre-fetch — sets cache so _now_utc() first call is instant."""
        t = self.get_internet_time()
        self._internet_time_cache = t  # None means all sources failed; still marks done

    # ── Legacy hardware ID ───────────────────────────────────────────────────

    def _get_legacy_hw_id(self) -> str:
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                ) as key:
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    return str(guid)
            except Exception:
                pass
        return socket.gethostname()

    def _derive_mac_key(self) -> bytes:
        return hmac.new(_APP_SECRET, self._hw_id.encode(), hashlib.sha256).digest()

    def _get_components(self) -> dict:
        """Collect hardware components once per process, then cache."""
        if self._components_cache is None:
            self._components_cache = collect_components()
        return self._components_cache

    # ── Security logging ─────────────────────────────────────────────────────

    def _log_security(self, event: str, details: str) -> None:
        try:
            self._sec_log.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{ts} UTC] [{event}] {details}\n"
            with open(self._sec_log, "a", encoding="utf-8") as f:
                f.write(line)
            logger.warning(f"SECURITY [{event}]: {details}")
        except Exception as e:
            logger.debug(f"Security log write failed: {e}")

    # ── Encode / decode ──────────────────────────────────────────────────────

    def _encode(self, data: dict) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":")).encode()
        ).decode()
        sig = hmac.new(self._mac_key, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def _decode(self, encoded: str) -> Optional[dict]:
        try:
            payload, sig = encoded.rsplit(".", 1)
            expected = hmac.new(
                self._mac_key, payload.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected):
                logger.warning("Trial: HMAC mismatch — tampered or different machine")
                return None
            return json.loads(base64.urlsafe_b64decode(payload).decode())
        except Exception as e:
            logger.debug(f"Trial decode error: {e}")
            return None

    # ── HKLM (write-once, admin-protected) ──────────────────────────────────

    def _read_hklm_init(self) -> Optional[dict]:
        if sys.platform != "win32":
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REG_HKLM_KEY) as key:
                encoded, _ = winreg.QueryValueEx(key, _REG_HKLM_VALUE)
                return self._decode(encoded)
        except Exception:
            return None

    def _write_hklm_init(self, data: dict) -> bool:
        """Write HKLM init record. Must be called while holding self._lock."""
        if sys.platform != "win32":
            return False
        if self._read_hklm_init() is not None:
            return True  # already written — do not overwrite
        try:
            import winreg
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, _REG_HKLM_KEY,
                0, winreg.KEY_WRITE,
            ) as key:
                winreg.SetValueEx(key, _REG_HKLM_VALUE, 0, winreg.REG_SZ, self._encode(data))
            logger.info("Trial: HKLM TrialInit written")
            return True
        except Exception as e:
            logger.debug(f"Trial HKLM write failed (need admin?): {e}")
            return False

    # ── HKCU ────────────────────────────────────────────────────────────────

    def _read_hkcu(self) -> Optional[dict]:
        if sys.platform != "win32":
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_HKCU_KEY) as key:
                encoded, _ = winreg.QueryValueEx(key, _REG_HKCU_VALUE)
                return self._decode(encoded)
        except Exception:
            return None

    def _write_hkcu(self, encoded: str) -> None:
        if sys.platform != "win32":
            return
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_HKCU_KEY) as key:
                winreg.SetValueEx(key, _REG_HKCU_VALUE, 0, winreg.REG_SZ, encoded)
        except Exception as e:
            logger.debug(f"Trial HKCU write failed: {e}")

    # ── Internal read (no lock — callers hold lock) ──────────────────────────

    def _read_unlocked(self) -> Optional[dict]:
        """
        Read and merge trial data from all three storage layers.
        Uses earliest install_date across all sources (reinstall-resistant).
        Must be called while holding self._lock.
        """
        candidates = []

        if self.trial_file.exists():
            try:
                d = self._decode(self.trial_file.read_text().strip())
                if d:
                    candidates.append(("file", d))
            except Exception as e:
                logger.debug(f"Trial file read error: {e}")

        d = self._read_hkcu()
        if d:
            candidates.append(("hkcu", d))

        d = self._read_hklm_init()
        if d:
            candidates.append(("hklm", d))

        if not candidates:
            return None

        def _parse_date(data):
            try:
                return datetime.fromisoformat(data.get("install_date", "9999-01-01"))
            except Exception:
                return datetime(9999, 1, 1)

        non_hklm = [(s, d) for s, d in candidates if s != "hklm"]
        if non_hklm:
            _, primary = max(non_hklm, key=lambda x: len(x[1].get("daily", {})))
        else:
            _, primary = candidates[0]

        hklm_data = next((d for s, d in candidates if s == "hklm"), None)
        if hklm_data:
            hklm_date = _parse_date(hklm_data)
            primary_date = _parse_date(primary)
            if hklm_date < primary_date:
                self._log_security(
                    "REINSTALL_DETECTED",
                    f"HKLM install_date {hklm_date.date()} < current {primary_date.date()} — restoring original",
                )
                primary["install_date"] = hklm_data["install_date"]
                if "fingerprint" in hklm_data:
                    primary.setdefault("fingerprint", hklm_data["fingerprint"])
                if "components" in hklm_data:
                    primary.setdefault("components", hklm_data["components"])

        return primary

    # ── Internal write (no lock — callers hold lock) ─────────────────────────

    def _write_unlocked(self, data: dict) -> None:
        """
        Persist data to all three storage layers.
        Must be called while holding self._lock.
        """
        encoded = self._encode(data)
        try:
            self.trial_file.write_text(encoded)
        except Exception as e:
            logger.debug(f"Trial file write error: {e}")
        self._write_hkcu(encoded)
        if "install_date" in data:
            init_record = {
                "install_date": data["install_date"],
                "fingerprint": data.get("fingerprint"),
                "components": data.get("components", {}),
            }
            self._write_hklm_init(init_record)

    # ── Internet time ────────────────────────────────────────────────────────

    def get_internet_time(self) -> Optional[datetime]:
        """Get UTC time from internet (3 sources, 5s total budget)."""
        import time
        import urllib.request
        from email.utils import parsedate_to_datetime

        sources = [
            "http://worldtimeapi.org/api/ip",
            "https://time.cloudflare.com/cdn-cgi/trace",
            "https://www.google.com",
        ]
        deadline = time.monotonic() + 5.0
        for url in sources:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Transkrib/2.0"})
                with urllib.request.urlopen(req, timeout=min(3.0, remaining)) as resp:
                    date_hdr = resp.headers.get("Date") or resp.headers.get("date")
                    if date_hdr:
                        dt = parsedate_to_datetime(date_hdr)
                        return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                continue
        return None

    def _now_utc(self, data: dict) -> datetime:
        """
        Current UTC time with clock rollback protection.
        Updates data["last_seen_time"] in-place (never goes backwards).
        Must be called while holding self._lock.
        Strategy: background prefetch started in __init__; if cache is ready use it,
        otherwise fall back to system time (non-blocking). On next call cache will be set.
        """
        system_time = datetime.now(timezone.utc).replace(tzinfo=None)
        internet_time = self._internet_time_cache  # None until prefetch completes
        if internet_time is not None:
            # Cache is populated — schedule background refresh for next session
            def _bg_refresh():
                t = self.get_internet_time()
                if t:
                    self._internet_time_cache = t
            threading.Thread(target=_bg_refresh, daemon=True).start()
        effective_time = internet_time if internet_time else system_time

        if "last_seen_time" in data:
            try:
                last_seen = datetime.fromisoformat(data["last_seen_time"])
                diff = (last_seen - effective_time).total_seconds()
                if diff > _ROLLBACK_TOLERANCE_SECONDS:
                    self._log_security(
                        "CLOCK_ROLLBACK",
                        f"effective={effective_time.date()} last_seen={last_seen.date()} "
                        f"delta={diff:.0f}s internet={'yes' if internet_time else 'no'}",
                    )
                    effective_time = last_seen
            except Exception:
                pass

        current_last = None
        try:
            current_last = datetime.fromisoformat(data.get("last_seen_time", "2000-01-01"))
        except Exception:
            pass
        if current_last is None or effective_time > current_last:
            data["last_seen_time"] = effective_time.strftime("%Y-%m-%dT%H:%M:%S")

        return effective_time

    # ── Fingerprint check (caller holds lock) ────────────────────────────────

    def _check_fingerprint(self, data: dict) -> bool:
        stored_components = data.get("components", {})
        if not stored_components:
            current = self._get_components()
            fp = build_fingerprint(current)
            if fp:
                data["components"] = current
                data["fingerprint"] = fp
            return True

        current_components = self._get_components()
        changes = count_component_changes(stored_components, current_components)

        if changes > BYPASS_THRESHOLD:
            data["bypass_blocked"] = True
            changed_keys = [
                k for k in ("cpu", "mac", "disk", "board")
                if stored_components.get(k) and current_components.get(k)
                and stored_components.get(k, "").upper() != current_components.get(k, "").upper()
            ]
            self._log_security(
                "BYPASS_DETECTED",
                f"{changes} hardware components changed simultaneously "
                f"(threshold={BYPASS_THRESHOLD}) — trial blocked. changed={changed_keys}",
            )
            self._write_unlocked(data)
            return False

        if changes > 0:
            changed_keys = [
                k for k in ("cpu", "mac", "disk", "board")
                if stored_components.get(k) and current_components.get(k)
                and stored_components.get(k, "").upper() != current_components.get(k, "").upper()
            ]
            self._log_security(
                "HW_CHANGE",
                f"{changes} component(s) changed (within tolerance). changed={changed_keys}",
            )

        return True

    # ── Public API (all methods hold lock) ───────────────────────────────────

    def init_trial(self) -> dict:
        """Initialize trial on first run. Idempotent."""
        with self._lock:
            existing = self._read_unlocked()
            if existing:
                logger.info("Trial: already initialized")
                # return status without re-acquiring lock
                return self._get_status_unlocked(existing)

            components = self._get_components()
            fingerprint = build_fingerprint(components)

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            data = {
                "v": 2,
                "install_date": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "machine_id": self._hw_id[:16],
                "fingerprint": fingerprint,
                "components": components,
                "last_seen_time": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "bypass_blocked": False,
                "daily": {},
            }
            # Get internet time and update last_seen_time
            internet_now = self._now_utc(data)
            data["install_date"] = internet_now.strftime("%Y-%m-%dT%H:%M:%S")
            self._write_unlocked(data)
            logger.info(f"Trial: initialized at {data['install_date']} fp={fingerprint}")
            return self._get_status_unlocked(data)

    def _get_status_unlocked(self, data: dict) -> dict:
        """Compute and return status from already-read data. Caller holds lock."""
        if data.get("bypass_blocked"):
            self._log_security("STATUS_CHECK", "bypass_blocked=True — returning blocked")
            return {
                "state": "blocked",
                "remaining_days": 0,
                "today_count": 0,
                "daily_limit": DAILY_LIMIT,
                "max_video_seconds": MAX_VIDEO_SECONDS,
                "warning": False,
                "message": "Попытка обхода зафиксирована. Пробный период заблокирован.",
            }

        if not self._check_fingerprint(data):
            return {
                "state": "blocked",
                "remaining_days": 0,
                "today_count": 0,
                "daily_limit": DAILY_LIMIT,
                "max_video_seconds": MAX_VIDEO_SECONDS,
                "warning": False,
                "message": "Попытка обхода зафиксирована. Пробный период заблокирован.",
            }

        now = self._now_utc(data)
        self._write_unlocked(data)

        install_date = datetime.fromisoformat(data.get("install_date", "2000-01-01"))
        elapsed = (now - install_date).days
        remaining = max(0, TRIAL_DAYS - elapsed)

        if elapsed >= TRIAL_DAYS:
            state = "expired"
        elif remaining <= WARNING_DAYS:
            state = "warning"
        else:
            state = "active"

        today = now.strftime("%Y-%m-%d")
        today_count = data.get("daily", {}).get(today, 0)

        return {
            "state": state,
            "remaining_days": remaining,
            "today_count": today_count,
            "daily_limit": DAILY_LIMIT,
            "max_video_seconds": MAX_VIDEO_SECONDS,
            "warning": remaining <= WARNING_DAYS and state != "expired",
        }

    def get_status(self) -> dict:
        """Return comprehensive trial status. Thread-safe."""
        with self._lock:
            data = self._read_unlocked()
            if not data:
                return {
                    "state": "new",
                    "remaining_days": TRIAL_DAYS,
                    "today_count": 0,
                    "daily_limit": DAILY_LIMIT,
                    "max_video_seconds": MAX_VIDEO_SECONDS,
                    "warning": False,
                }
            return self._get_status_unlocked(data)

    def can_process(self) -> tuple[bool, str]:
        """Check if video processing is allowed. Returns (allowed, reason). Thread-safe."""
        status = self.get_status()
        state = status["state"]
        if state == "new":
            return False, "Trial not initialized"
        if state in ("expired", "blocked"):
            return False, status.get("message", "Пробный период завершён")
        if status["today_count"] >= DAILY_LIMIT:
            return False, f"Дневной лимит достигнут ({status['today_count']}/{DAILY_LIMIT} видео)"
        return True, "ok"

    def record_video(self) -> None:
        """Increment today's video counter. Thread-safe."""
        with self._lock:
            data = self._read_unlocked()
            if not data:
                return
            now = self._now_utc(data)  # uses stored last_seen_time for rollback check
            today = now.strftime("%Y-%m-%d")
            daily = data.get("daily", {})
            daily[today] = daily.get(today, 0) + 1
            cutoff = (now - timedelta(days=8)).strftime("%Y-%m-%d")
            data["daily"] = {k: v for k, v in daily.items() if k > cutoff}
            self._write_unlocked(data)
            logger.info(f"Trial: recorded video {today} count={data['daily'][today]}")
