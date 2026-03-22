"""File naming utilities extracted from transkrib/main.py."""

import re
from pathlib import Path


def safe_filename(name: str, max_len: int = 80) -> str:
    """Makes a string safe for use as a filename."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    return safe[:max_len].strip("_ ")


def get_next_result_number(result_dir: Path) -> int:
    """Determines next sequential number (NNN) for result files."""
    if not result_dir.exists():
        return 1
    max_num = 0
    for f in result_dir.glob("*.mp4"):
        match = re.match(r"^(\d{3})_", f.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1
