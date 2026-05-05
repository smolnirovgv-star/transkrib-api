"""Startup tasks: update critical dependencies before server launch."""
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def update_critical_dependencies():
    """Update critical dependencies at server startup.
    yt-dlp requires frequent updates as YouTube changes its API."""
    try:
        # Ensure ffmpeg is available
        subprocess.run(
            ["apt-get", "install", "-y", "ffmpeg"],
            capture_output=True, timeout=60
        )
        logger.info("ffmpeg install attempted")

        # Remove broken OAuth2 plugin (archived 17.01.2026)
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "yt-dlp-youtube-oauth2"],
            capture_output=True, timeout=30
        )
        logger.info("Removed yt-dlp-youtube-oauth2 plugin (if existed)")

        # Update yt-dlp to latest NIGHTLY (better PO Token + client support)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "--pre",
             "yt-dlp[default,curl-cffi]"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            logger.info("yt-dlp updated successfully (nightly)")
        else:
            logger.warning("yt-dlp update failed: %s", result.stderr[:300])

        # Ensure youtube-transcript-api is installed
        result2 = subprocess.run(
            [sys.executable, "-m", "pip", "install", "youtube-transcript-api"],
            capture_output=True, text=True, timeout=60
        )
        if result2.returncode == 0:
            logger.info("youtube-transcript-api OK: %s", result2.stdout.strip()[-100:])
        else:
            logger.error("youtube-transcript-api install FAILED: %s", result2.stderr[:300])

    except Exception as e:
        logger.warning("Failed to update dependencies: %s", e)
