# Trial Protection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-layer trial period protection against bypass: hardware fingerprint (CPU+MAC+disk+board), HKLM/HKCU/file tri-storage, clock rollback detection, bypass detection on hardware changes >2, security logging.

**Architecture:** New `fingerprint.py` collects 4 hardware IDs (stdlib + ctypes + subprocess/wmic). Updated `trial.py` v2 stores data in 3 locations (file, HKCU, HKLM), detects clock rollback via cached last-seen time, blocks trial if >2 hardware components change, logs all security events to `security.log`. Finally rebuild backend.exe + NSIS installer.

**Tech Stack:** Python 3.11, winreg, ctypes (GetVolumeInformationW), subprocess (wmic/powershell), hmac/hashlib, FastAPI, PyInstaller, electron-builder/NSIS

---

## Task 1: Create `app/backend/app/fingerprint.py`

**Files:**
- Create: `app/backend/app/fingerprint.py`

**Step 1: Write the file**

```python
"""
Hardware fingerprint collector for Transkrib trial protection.

Collects CPU ProcessorId, MAC address, disk C: volume serial,
and motherboard serial number using stdlib only (no extra deps).
Windows only — returns empty dict on other platforms.
"""

import sys
import uuid
import ctypes
import hashlib
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("video_processor.fingerprint")

# Strings that indicate no real serial is available (VMs, generic OEM)
_INVALID = {
    "", "none", "n/a", "na", "default string", "to be filled by o.e.m.",
    "system serial number", "not specified", "not applicable",
    "0", "0000000000000000", "fill by oem", "ffffffffffffffff", "unknown",
    "null",
}

# If more than this many components change between snapshots → bypass attempt
BYPASS_THRESHOLD = 2


def _clean(val: Optional[str]) -> Optional[str]:
    """Normalize and reject placeholder serial numbers."""
    if not val:
        return None
    val = val.strip()
    if val.lower() in _INVALID:
        return None
    return val


def _run_wmic(args: list) -> Optional[str]:
    """Run wmic with /value flag, return parsed value or None."""
    try:
        result = subprocess.run(
            ["wmic"] + args + ["/value"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                return _clean(line.split("=", 1)[1])
    except Exception as e:
        logger.debug(f"wmic {args}: {e}")
    return None


def _run_ps(script: str) -> Optional[str]:
    """Run PowerShell one-liner, return stripped output or None."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", script,
            ],
            capture_output=True, text=True, timeout=6,
            creationflags=0x08000000,
        )
        return _clean(result.stdout.strip())
    except Exception as e:
        logger.debug(f"PS '{script[:60]}': {e}")
    return None


def get_cpu_id() -> Optional[str]:
    """CPU ProcessorId: wmic → Win32_Processor CIM → WMI fallback."""
    val = _run_wmic(["cpu", "get", "ProcessorId"])
    if not val:
        val = _run_ps("(Get-CimInstance Win32_Processor).ProcessorId")
    if not val:
        val = _run_ps("(Get-WmiObject Win32_Processor).ProcessorId")
    return val


def get_mac_address() -> Optional[str]:
    """Primary MAC address via uuid.getnode() (stdlib)."""
    try:
        mac = uuid.getnode()
        # If multicast bit is set, uuid generated a random address — ignore
        if mac and not (mac >> 40 & 1):
            return f"{mac:012x}"
    except Exception as e:
        logger.debug(f"MAC: {e}")
    return None


def get_disk_serial() -> Optional[str]:
    """C: drive volume serial number via Win32 GetVolumeInformationW."""
    try:
        serial = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"),
            None, 0,
            ctypes.byref(serial),
            None, None, None, 0,
        )
        if ok and serial.value:
            return f"{serial.value:08X}"
    except Exception as e:
        logger.debug(f"Disk serial: {e}")
    return None


def get_board_serial() -> Optional[str]:
    """Motherboard SerialNumber: wmic → CIM → WMI fallback."""
    val = _run_wmic(["baseboard", "get", "SerialNumber"])
    if not val:
        val = _run_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber")
    if not val:
        val = _run_ps("(Get-WmiObject Win32_BaseBoard).SerialNumber")
    return val


def collect_components() -> dict:
    """
    Collect all four hardware identifiers.

    Returns dict with keys 'cpu', 'mac', 'disk', 'board'.
    Values are None when a component is unavailable.
    Always returns empty-valued dict on non-Windows.
    """
    if sys.platform != "win32":
        return {"cpu": None, "mac": None, "disk": None, "board": None}

    components = {
        "cpu":   get_cpu_id(),
        "mac":   get_mac_address(),
        "disk":  get_disk_serial(),
        "board": get_board_serial(),
    }
    available = sum(1 for v in components.values() if v)
    logger.debug(
        f"Fingerprint: {available}/4 components — "
        + ", ".join(k for k, v in components.items() if v)
    )
    return components


def build_fingerprint(components: dict) -> Optional[str]:
    """
    Build a 32-char SHA-256 fingerprint from available components.

    Returns None if fewer than 2 components have real values
    (not enough signal for reliable identification).
    """
    valid = {k: v for k, v in components.items() if v}
    if len(valid) < 2:
        logger.warning(
            f"Fingerprint: only {len(valid)} valid components — cannot fingerprint"
        )
        return None
    parts = sorted(f"{k}:{v.upper()}" for k, v in valid.items())
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def count_component_changes(old: dict, new: dict) -> int:
    """
    Count how many components changed between two snapshots.

    Only counts components where BOTH old and new have a real value
    (a value appearing/disappearing may be transient, e.g. VPN MAC).
    """
    changes = 0
    for key in ("cpu", "mac", "disk", "board"):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val and new_val and old_val.upper() != new_val.upper():
            changes += 1
            logger.debug(f"HW change: {key} {old_val[:8]}… → {new_val[:8]}…")
    return changes
```

**Step 2: Verify file created correctly**

Open `app/backend/app/fingerprint.py` — confirm it has all 6 functions: `_clean`, `_run_wmic`, `_run_ps`, `get_cpu_id`, `get_mac_address`, `get_disk_serial`, `get_board_serial`, `collect_components`, `build_fingerprint`, `count_component_changes`.

---

## Task 2: Rewrite `app/backend/app/trial.py`

**Files:**
- Modify: `app/backend/app/trial.py` (full replacement)

**Step 1: Replace the entire file**

```python
"""
Trial period manager for Transkrib Desktop — v2.

Multi-layer protection:
  - Hardware fingerprint: CPU ID + MAC + disk serial + motherboard serial
  - Tri-storage: file (primary) + HKCU registry + HKLM registry (admin)
  - Clock rollback detection via cached last-seen internet time
  - Bypass detection: >2 hardware components changed → permanent block
  - Security event log: AppData\\Roaming\\Transkrib\\security.log

All data is HMAC-signed and machine-bound (stdlib only).
"""

import os
import sys
import hmac
import json
import socket
import hashlib
import base64
import logging
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

# App secret — must stay constant across builds
_APP_SECRET = b"transkrib-trial-v1-2024-7f3a9e2c8b1d"

TRIAL_DAYS = 7
DAILY_LIMIT = 3
WARNING_DAYS = 2
MAX_VIDEO_SECONDS = 1800  # 30 minutes

# Registry locations
_REG_HKCU_KEY   = r"SOFTWARE\Transkrib"
_REG_HKCU_VALUE = "TrialData"         # full data (daily counters etc.)
_REG_HKLM_KEY   = r"SOFTWARE\Transkrib"
_REG_HKLM_VALUE = "TrialInit"         # write-once init record (admin-protected)

# Clock rollback tolerance
_ROLLBACK_TOLERANCE_SECONDS = 300  # 5 minutes


class TrialManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trial_file = data_dir / "trial.dat"
        # Security log lives one level up from storage/ (AppData\Roaming\Transkrib\)
        self._sec_log = data_dir.parent / "security.log"
        self._hw_id = self._get_legacy_hw_id()
        self._mac_key = self._derive_mac_key()

    # ── Legacy hardware ID (backwards compat) ───────────────────────────────

    def _get_legacy_hw_id(self) -> str:
        """Windows MachineGuid, fallback hostname."""
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

    # ── Security logging ────────────────────────────────────────────────────

    def _log_security(self, event: str, details: str) -> None:
        """Append a timestamped security event to security.log."""
        try:
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{ts} UTC] [{event}] {details}\n"
            with open(self._sec_log, "a", encoding="utf-8") as f:
                f.write(line)
            logger.warning(f"SECURITY [{event}]: {details}")
        except Exception as e:
            logger.debug(f"Security log write failed: {e}")

    # ── Encode / decode ─────────────────────────────────────────────────────

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

    # ── HKLM (write-once, admin-protected) ─────────────────────────────────

    def _read_hklm_init(self) -> Optional[dict]:
        """Read install-time record from HKLM (survives reinstalls, admin-protected)."""
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
        """Write install-time record to HKLM (only if not already set)."""
        if sys.platform != "win32":
            return False
        if self._read_hklm_init() is not None:
            return True  # already written, do not overwrite
        try:
            import winreg
            key = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, _REG_HKLM_KEY,
                0, winreg.KEY_WRITE,
            )
            with key:
                winreg.SetValueEx(key, _REG_HKLM_VALUE, 0, winreg.REG_SZ, self._encode(data))
            logger.info("Trial: HKLM TrialInit written")
            return True
        except Exception as e:
            logger.debug(f"Trial HKLM write failed (need admin?): {e}")
            return False

    # ── HKCU ───────────────────────────────────────────────────────────────

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

    # ── Tri-storage read (merge sources, use earliest install_date) ─────────

    def _read(self) -> Optional[dict]:
        """
        Read trial data from all three locations.
        Returns merged data using the EARLIEST install_date found
        (protects against reinstall-based date reset).
        """
        candidates = []

        # 1. File
        if self.trial_file.exists():
            try:
                d = self._decode(self.trial_file.read_text().strip())
                if d:
                    candidates.append(("file", d))
            except Exception as e:
                logger.debug(f"Trial file read error: {e}")

        # 2. HKCU
        d = self._read_hkcu()
        if d:
            candidates.append(("hkcu", d))

        # 3. HKLM (install-time only record — may have earlier install_date)
        d = self._read_hklm_init()
        if d:
            candidates.append(("hklm", d))

        if not candidates:
            return None

        # Pick the candidate with the EARLIEST install_date
        def _parse_date(data):
            try:
                return datetime.fromisoformat(data.get("install_date", "9999-01-01"))
            except Exception:
                return datetime(9999, 1, 1)

        # Start from the record with most detail (file/hkcu), then
        # override install_date / components / fingerprint from the oldest source
        primary_source, primary = max(
            [(s, d) for s, d in candidates if s != "hklm"],
            key=lambda x: len(x[1].get("daily", {})),
            default=("hklm", candidates[0][1]),
        )

        # Check if HKLM has an earlier install_date (reinstall detected)
        hklm_data = next((d for s, d in candidates if s == "hklm"), None)
        if hklm_data:
            hklm_date = _parse_date(hklm_data)
            primary_date = _parse_date(primary)
            if hklm_date < primary_date:
                # HKLM has older date → user reinstalled, restore original date
                self._log_security(
                    "REINSTALL_DETECTED",
                    f"HKLM install_date {hklm_date.date()} < current {primary_date.date()} — restoring original"
                )
                primary["install_date"] = hklm_data["install_date"]
                # Also restore original fingerprint/components if present in HKLM
                if "fingerprint" in hklm_data:
                    primary.setdefault("fingerprint", hklm_data["fingerprint"])
                if "components" in hklm_data:
                    primary.setdefault("components", hklm_data["components"])

        # If file was missing, restore it from registry
        if primary_source != "file" or not self.trial_file.exists():
            encoded = self._encode(primary)
            try:
                self.trial_file.write_text(encoded)
            except Exception:
                pass

        return primary

    # ── Tri-storage write ───────────────────────────────────────────────────

    def _write(self, data: dict) -> None:
        encoded = self._encode(data)
        # 1. File
        try:
            self.trial_file.write_text(encoded)
        except Exception as e:
            logger.debug(f"Trial file write error: {e}")
        # 2. HKCU
        self._write_hkcu(encoded)
        # 3. HKLM init (only on first write — contains install_date + components)
        if "install_date" in data:
            init_record = {
                "install_date": data["install_date"],
                "fingerprint": data.get("fingerprint"),
                "components": data.get("components", {}),
            }
            self._write_hklm_init(init_record)

    # ── Internet time with rollback detection ───────────────────────────────

    def get_internet_time(self) -> Optional[datetime]:
        """Get UTC time from internet (3 sources). Returns None if offline."""
        import urllib.request
        from email.utils import parsedate_to_datetime

        sources = [
            "http://worldtimeapi.org/api/ip",
            "https://time.cloudflare.com/cdn-cgi/trace",
            "https://www.google.com",  # Date: header always present
        ]
        for url in sources:
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Transkrib/2.0"}
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    date_hdr = resp.headers.get("Date") or resp.headers.get("date")
                    if date_hdr:
                        dt = parsedate_to_datetime(date_hdr)
                        return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                continue
        return None

    def _now_utc(self, data: Optional[dict] = None) -> datetime:
        """
        Current UTC time with clock rollback protection.

        If internet time is available: compare to last_seen_time stored in data.
        If system time < last_seen_time - tolerance: rollback detected → use last_seen_time.
        Updates last_seen_time in data dict (caller must _write to persist).
        """
        system_time = datetime.utcnow()
        internet_time = self.get_internet_time()
        effective_time = internet_time if internet_time else system_time

        if data is not None and "last_seen_time" in data:
            try:
                last_seen = datetime.fromisoformat(data["last_seen_time"])
                diff = (last_seen - effective_time).total_seconds()
                if diff > _ROLLBACK_TOLERANCE_SECONDS:
                    self._log_security(
                        "CLOCK_ROLLBACK",
                        f"effective={effective_time.date()} last_seen={last_seen.date()} "
                        f"delta={diff:.0f}s internet={'yes' if internet_time else 'no'}"
                    )
                    effective_time = last_seen  # use the later known-good time
            except Exception:
                pass

        # Update last_seen_time in data to current (don't go backwards)
        if data is not None:
            current_last = None
            try:
                current_last = datetime.fromisoformat(data.get("last_seen_time", "2000-01-01"))
            except Exception:
                pass
            if current_last is None or effective_time > current_last:
                data["last_seen_time"] = effective_time.strftime("%Y-%m-%dT%H:%M:%S")

        return effective_time

    # ── Fingerprint check ───────────────────────────────────────────────────

    def _check_fingerprint(self, data: dict) -> bool:
        """
        Compare current hardware to stored fingerprint.
        If >BYPASS_THRESHOLD components changed → mark bypass_blocked, log, return False.
        Returns True if hardware is within tolerance.
        """
        stored_components = data.get("components", {})
        if not stored_components:
            # No fingerprint stored yet (v1 data) — store now and allow
            current = collect_components()
            fp = build_fingerprint(current)
            if fp:
                data["components"] = current
                data["fingerprint"] = fp
            return True

        current_components = collect_components()
        changes = count_component_changes(stored_components, current_components)

        if changes > BYPASS_THRESHOLD:
            data["bypass_blocked"] = True
            self._log_security(
                "BYPASS_DETECTED",
                f"{changes} hardware components changed simultaneously "
                f"(threshold={BYPASS_THRESHOLD}) — trial blocked. "
                f"old={stored_components} new={current_components}"
            )
            self._write(data)
            return False

        if changes > 0:
            self._log_security(
                "HW_CHANGE",
                f"{changes} component(s) changed (within tolerance). "
                f"old={stored_components} new={current_components}"
            )

        return True

    # ── Trial lifecycle ─────────────────────────────────────────────────────

    def init_trial(self) -> dict:
        """Initialize trial on first run. No-op if already initialized."""
        existing = self._read()
        if existing:
            logger.info("Trial: already initialized")
            return self.get_status()

        # Collect hardware fingerprint
        components = collect_components()
        fingerprint = build_fingerprint(components)

        now_data: dict = {}
        now = self._now_utc(now_data)

        data = {
            "v": 2,
            "install_date": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "machine_id": self._hw_id[:16],
            "fingerprint": fingerprint,
            "components": components,
            "last_seen_time": now_data.get("last_seen_time", now.strftime("%Y-%m-%dT%H:%M:%S")),
            "bypass_blocked": False,
            "daily": {},
        }
        self._write(data)
        logger.info(f"Trial: initialized at {data['install_date']} fp={fingerprint}")
        return self.get_status()

    def get_status(self) -> dict:
        """Return comprehensive trial status."""
        data = self._read()

        if not data:
            return {
                "state": "new",
                "remaining_days": TRIAL_DAYS,
                "today_count": 0,
                "daily_limit": DAILY_LIMIT,
                "max_video_seconds": MAX_VIDEO_SECONDS,
                "warning": False,
            }

        # Check permanent bypass block
        if data.get("bypass_blocked"):
            self._log_security("STATUS_CHECK", "bypass_blocked=True → returning blocked")
            return {
                "state": "blocked",
                "remaining_days": 0,
                "today_count": 0,
                "daily_limit": DAILY_LIMIT,
                "max_video_seconds": MAX_VIDEO_SECONDS,
                "warning": False,
                "message": "Попытка обхода зафиксирована. Пробный период заблокирован.",
            }

        # Fingerprint check (updates data in-place, writes if needed)
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

        # Time calculation with rollback protection
        now = self._now_utc(data)
        # Persist updated last_seen_time
        self._write(data)

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

    def can_process(self) -> tuple[bool, str]:
        """Check if video processing is allowed. Returns (allowed, reason)."""
        status = self.get_status()
        state = status["state"]
        if state == "new":
            return False, "Trial not initialized"
        if state in ("expired", "blocked"):
            msg = status.get("message", "Пробный период завершён")
            return False, msg
        if status["today_count"] >= DAILY_LIMIT:
            return False, f"Дневной лимит достигнут ({status['today_count']}/{DAILY_LIMIT} видео)"
        return True, "ok"

    def record_video(self) -> None:
        """Increment today's video count."""
        data = self._read()
        if not data:
            return
        now_data: dict = {}
        now = self._now_utc(now_data)
        today = now.strftime("%Y-%m-%d")
        daily = data.get("daily", {})
        daily[today] = daily.get(today, 0) + 1
        cutoff = (now - timedelta(days=8)).strftime("%Y-%m-%d")
        data["daily"] = {k: v for k, v in daily.items() if k > cutoff}
        if "last_seen_time" in now_data:
            data["last_seen_time"] = now_data["last_seen_time"]
        self._write(data)
        logger.info(f"Trial: recorded video {today} count={data['daily'][today]}")
```

**Step 2: Verify file saved correctly**

Check that `app/backend/app/trial.py` starts with `"""Trial period manager for Transkrib Desktop — v2.` and contains class `TrialManager` with all methods.

---

## Task 3: Integrate TrialManager into standalone_server.py

**Files:**
- Modify: `app/backend/standalone_server.py`

**Step 1: Add TrialManager import**

After line 92 (`from app.license import LicenseManager`), add:

```python
from app.trial import TrialManager
```

**Step 2: Add TrialManager initialization in lifespan**

After the license manager block (after line ~159 `app.state.license_manager = license_manager`), add:

```python
    # Initialize trial manager
    trial_manager = TrialManager(settings.storage_dir)
    trial_manager.init_trial()
    app.state.trial_manager = trial_manager
    trial_status = trial_manager.get_status()
    logger.info(f"Trial status: {trial_status['state']} ({trial_status['remaining_days']} days remaining)")
```

**Step 3: Add trial API endpoints**

After the `/api/system/activate` endpoint, add:

```python
@app.get("/api/system/trial")
async def get_trial_status():
    """Get trial period status."""
    trial_manager: TrialManager = app.state.trial_manager
    return trial_manager.get_status()


@app.post("/api/system/trial/record")
async def record_trial_video():
    """Record a processed video against trial limits (call after successful processing)."""
    trial_manager: TrialManager = app.state.trial_manager
    allowed, reason = trial_manager.can_process()
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    trial_manager.record_video()
    return {"recorded": True}
```

---

## Task 4: Update backend.spec (add fingerprint module)

**Files:**
- Modify: `app/backend/backend.spec`

**Step 1: Add fingerprint to hiddenimports**

Find the `hiddenimports` list in `backend.spec`. After `'app.license',` (around line 108), add:

```python
        'app.trial',
        'app.fingerprint',
```

(Both are new modules that PyInstaller won't auto-detect since they're not imported at module level in the entry point.)

---

## Task 5: Rebuild backend.exe

**Files:**
- Output: `app/backend/dist/backend/backend.exe`

**Step 1: Run PyInstaller**

```
cd app/backend
pyinstaller backend.spec --clean --noconfirm
```

Expected output ends with:
```
Building COLLECT COLLECT-00.toc
Building COLLECT COLLECT-00.toc completed successfully.
```

Dist output: `app/backend/dist/backend/` (~600-800 MB)

**Step 2: Quick smoke test**

```
app/backend/dist/backend/backend.exe
```

Should see `Transkrib Standalone Server starting...` in console and respond to `curl http://127.0.0.1:8000/api/system/health`.

Kill with Ctrl+C after confirming.

---

## Task 6: Rebuild Electron app + NSIS installer

**Files:**
- Output: `app/platforms/desktop_windows/release/Transkrib-Setup-*.exe`

**Step 1: Install npm deps (if needed)**

```
cd app/platforms/desktop_windows
npm install
```

**Step 2: Build Electron renderer (Vite)**

```
cd app/platforms/desktop_windows
npm run build
```

Expected: `dist/` folder created with renderer bundle.

**Step 3: Package with electron-builder**

```
cd app/platforms/desktop_windows
npx electron-builder --win --x64
```

Expected output:
```
  • building        target=nsis file=Transkrib-Setup-x.x.x.exe
  • building block map
```

Final artifact: `release/Transkrib-Setup-x.x.x.exe`

**Step 4: Verify installer exists**

Check `app/platforms/desktop_windows/release/` for `Transkrib-Setup-*.exe` file.

---

## Summary of Changes

| File | Change |
|---|---|
| `app/backend/app/fingerprint.py` | NEW — hardware ID collector |
| `app/backend/app/trial.py` | REWRITE — v2 with tri-storage, fingerprint, rollback, bypass detection, security log |
| `app/backend/standalone_server.py` | ADD — TrialManager init + 2 API endpoints |
| `app/backend/backend.spec` | ADD — `app.trial`, `app.fingerprint` to hiddenimports |

**Security events logged to `AppData\Roaming\Transkrib\security.log`:**
- `REINSTALL_DETECTED` — HKLM date older than current data
- `CLOCK_ROLLBACK` — effective time < last_seen_time
- `BYPASS_DETECTED` — >2 hardware components changed simultaneously
- `HW_CHANGE` — 1-2 components changed (within tolerance, logged only)
- `STATUS_CHECK` — checked while bypass_blocked=True
