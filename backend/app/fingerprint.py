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
    "", "none", "n/a", "na", "default string",
    "to be filled by o.e.m.", "to be filled by o.e.m",
    "system serial number", "not specified", "not applicable",
    "chassis serial number", "base board serial number",
    "0", "0x00000000", "00000000", "0000000000000000",
    "fill by oem", "ffffffffffffffff", "unknown", "null", "invalid",
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
    """Run wmic with /value flag, return the specific property value or None."""
    try:
        result = subprocess.run(
            ["wmic"] + args + ["/value"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return None
        # The last arg is the property name (e.g. "ProcessorId", "SerialNumber")
        target_key = args[-1].lower()
        for line in result.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                key, _, value = line.partition("=")
                if key.strip().lower() == target_key:
                    return _clean(value)
        # Fallback: return any non-empty value after = (handles locale differences)
        for line in result.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                _, _, value = line.partition("=")
                cleaned = _clean(value)
                if cleaned:
                    return cleaned
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
            creationflags=subprocess.CREATE_NO_WINDOW,
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
            return f"{mac:012X}"
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
    Collect all four hardware identifiers IN PARALLEL to minimise startup latency.

    Returns dict with keys 'cpu', 'mac', 'disk', 'board'.
    Values are None when a component is unavailable.
    Always returns empty-valued dict on non-Windows.
    """
    if sys.platform != "win32":
        return {"cpu": None, "mac": None, "disk": None, "board": None}

    import concurrent.futures
    # Run all four collectors concurrently — wmic startup overhead paid once
    with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="hwfp") as ex:
        f_cpu   = ex.submit(get_cpu_id)
        f_mac   = ex.submit(get_mac_address)
        f_disk  = ex.submit(get_disk_serial)
        f_board = ex.submit(get_board_serial)
        components = {
            "cpu":   f_cpu.result(),
            "mac":   f_mac.result(),
            "disk":  f_disk.result(),
            "board": f_board.result(),
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
            logger.debug(f"HW change: {key} {old_val[:6]}… → {new_val[:6]}…")
    return changes
