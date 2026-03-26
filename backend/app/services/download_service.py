"""Video download via yt-dlp. Extracted from transkrib/main.py."""

import sys
import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Callable

logger = logging.getLogger("video_processor.download")


def _get_ytdlp_cmd() -> list[str]:
    """
    Get yt-dlp command for subprocess.

    When frozen with PyInstaller, sys.executable points to backend.exe,
    so we need to use the bundled yt-dlp.exe instead.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller frozen mode — use bundled yt-dlp.exe
        ytdlp_path = os.environ.get("YTDLP_PATH")
        if ytdlp_path and Path(ytdlp_path).exists():
            return [ytdlp_path]

        # Fallback: look in _MEIPASS
        base = Path(sys._MEIPASS)
        ytdlp_exe = base / "yt-dlp.exe"
        if ytdlp_exe.exists():
            return [str(ytdlp_exe)]

        logger.error("yt-dlp.exe not found in frozen bundle")
        raise FileNotFoundError("yt-dlp.exe not found")

    # Not frozen — use python -m yt_dlp
    return [sys.executable, "-m", "yt_dlp"]


class DownloadService:
    def __init__(self, ffmpeg_path: str):
        self._ffmpeg_path = ffmpeg_path

    def download_url(
        self,
        url: str,
        output_dir: Path,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[Path | None, str]:
        """Downloads video from URL via yt-dlp. Returns (file_path, title)."""
        logger.info(f"Downloading: {url}")
        title = self.get_title(url)
        output_template = str(output_dir / "%(title)s.%(ext)s")

        cmd = [
            *_get_ytdlp_cmd(),
            "-S", "vcodec:h264,acodec:aac",
            "--merge-output-format", "mp4",
            "--output", output_template,
            "--no-playlist",
            "--quiet", "--progress",
            # Обход блокировки YouTube на серверах
            "--extractor-retries", "3",
            "--socket-timeout", "30",
            "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--add-header", "Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "--add-header", "Accept-Language:en-us,en;q=0.5",
            "--add-header", "Sec-Fetch-Mode:navigate",
            "--extractor-args", "youtube:player_client=web,android",
        ]
        if self._ffmpeg_path:
            cmd.extend(["--ffmpeg-location", str(Path(self._ffmpeg_path).parent)])
        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Download error {url}: {result.stderr[-500:]}")
            return None, title

        all_files = [f for f in output_dir.iterdir() if f.is_file()]
        if not all_files:
            return None, title
        downloaded = max(all_files, key=lambda f: f.stat().st_mtime)

        if on_progress:
            on_progress(100.0)
        return downloaded, title

    def get_title(self, url: str) -> str:
        """Gets video title via yt-dlp --dump-json."""
        cmd = [
            *_get_ytdlp_cmd(),
            "--dump-json", "--no-playlist", "--quiet", url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                info = json.loads(result.stdout)
                return info.get("title", "unknown")
            except json.JSONDecodeError:
                pass
        return "unknown"

    @staticmethod
    def validate_url(url: str) -> bool:
        """Basic URL validation for supported platforms."""
        url_lower = url.lower().strip()
        supported = [
            "youtube.com", "youtu.be",
            "vk.com", "vkvideo.ru",
            "rutube.ru",
        ]
        return any(domain in url_lower for domain in supported) or url_lower.startswith("http")
